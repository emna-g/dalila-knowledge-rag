"""Voix vers texte (BF7, BNF3, BNF8) : faster-whisper (Whisper sur CTranslate2, licence MIT), local, sur processeur.

    from dalila.voix.reconnaissance import transcrire
    transcrire(octets_audio, lang="fr") -> {"texte", "langue", "confiance", "duree_audio_s", "duree_s"}

L'audio (webm, ogg, mp3, wav... tel qu'envoyé par le navigateur) est décodé EN MÉMOIRE et jamais écrit sur disque ni
gardé (BNF8). Le texte reconnu est rendu à l'interface, qui l'affiche avant de l'envoyer à /carte/chatbot (le visiteur
peut le corriger). Whisper détecte la langue ; si l'interface donne une langue qu'il connaît, elle est imposée
(plus rapide et plus sûr). Les dialectes (tunisien, algérien, libyen) sont laissés à la détection.

Deux modèles : Whisper `small` détecte la langue et transcrit fr, en, de, tr ; l'arabe et les dialectes sont transcrits
par whisper-small-tunisian-derja-ct2 (le modèle « whisper-tn-ct2 » du cahier des charges, Apache 2.0) : sur 28 vrais
extraits tunisiens (LinTO, test), 32 % de mots faux contre 69 % pour Whisper `small`, à la même vitesse ; il garde le
français mêlé au tunisien. Seul, il prend l'allemand et le turc pour de l'arabe : d'où le partage.

Réglages (.env) : DALILA_STT (modèle général, défaut « small »), DALILA_STT_ARABE (modèle de l'arabe et des dialectes,
défaut TheBiggyBang/whisper-small-tunisian-derja-ct2 ; vide : le modèle général), DALILA_LLM_FILS (fils, défaut 8).
"""
import io, os, threading, time
from dalila.config import MODELES

MODELE_STT = os.environ.get("DALILA_STT", "small")
MODELE_ARABE = os.environ.get("DALILA_STT_ARABE", "TheBiggyBang/whisper-small-tunisian-derja-ct2") or MODELE_STT
LANGUES_WHISPER = {"fr", "en", "ar", "de", "tr"}
DIALECTES = {"aeb", "arq", "ayl", "tn", "dz", "ly"}
TAILLE_MAX = 5 * 1024 * 1024   # octets : ~1 min de parole compressée
DUREE_MAX_S = 60
PART_ARABE = 0.15      # probabilité de l'arabe au-delà de laquelle le modèle tunisien transcrit (français mêlé compris)
OPTIONS = dict(beam_size=1, vad_filter=True, condition_on_previous_text=False, temperature=0.0, max_new_tokens=160)
# une seule température : un passage qui boucle n'est pas relancé 5 fois (un extrait a pris 40 s) ; une question tient
# dans 160 jetons
_modeles, _verrou = {}, threading.Lock()


def modele(nom=None):
    nom = nom or MODELE_STT
    with _verrou:
        if nom not in _modeles:
            from faster_whisper import WhisperModel
            _modeles[nom] = WhisperModel(nom, device="cpu", compute_type="int8",
                                         cpu_threads=int(os.environ.get("DALILA_LLM_FILS", "8")),
                                         download_root=str(MODELES / "whisper"))
        return _modeles[nom]


class AudioInvalide(ValueError):
    pass


_lieux_cache = {}


LANGUES_VOCABULAIRE = {"fr", "en", "de", "tr"}


def vocabulaire():
    """Noms propres que Whisper écrit mal sans aide (« Janduba », « S-Fax ») : gouvernorats de la base (noms français)
    et sigles, passés comme mots favorisés (hotwords), SEULEMENT pour fr, en, de, tr. En arabe et en dialecte, Whisper
    est moins sûr et ces noms deviennent des suggestions : « عسلامة كيفاش تنجم تعاوني » a été reconnu « lot Sfax Sidi
    Bouzid ». Lus une fois ; base injoignable : rien (la reconnaissance marche sans)."""
    if "v" not in _lieux_cache:
        try:
            from dalila.traitement.base import q
            noms = [r["nom_fr"] for r in q("SELECT nom_fr FROM dalila_gouvernorats")]
            _lieux_cache["v"] = " ".join(["AFI", "APII", "TIA", "FIPA", *noms])
        except Exception:  # noqa: BLE001
            _lieux_cache["v"] = None
    return _lieux_cache["v"]


def _decoder(audio: bytes):
    """Octets audio (tout format lu par FFmpeg) -> échantillons 16 kHz mono, en mémoire. Fait ici plutôt que par
    faster-whisper, dont le décodeur appelle une option retirée des versions récentes de PyAV."""
    import av, numpy as np
    morceaux = []
    with av.open(io.BytesIO(audio), mode="r") as conteneur:
        flux = conteneur.streams.audio[0]
        reech = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
        for trame in conteneur.decode(flux):
            for t in reech.resample(trame):
                morceaux.append(t.to_ndarray().reshape(-1))
        for t in reech.resample(None):
            morceaux.append(t.to_ndarray().reshape(-1))
    if not morceaux:
        raise AudioInvalide("audio vide")
    return np.concatenate(morceaux).astype(np.float32) / 32768.0


def transcrire(audio: bytes, lang=None, nom=None):
    if not audio:
        raise AudioInvalide("audio vide")
    if len(audio) > TAILLE_MAX:
        raise AudioInvalide("audio trop long")
    debut = time.time()
    lang = (lang or "").strip().lower()
    # dialectes maghrébins : Whisper n'a pas de code pour eux et, laissé libre, prend le tunisien pour du polonais ;
    # imposer l'arabe le fait écrire en lettres arabes, que l'agent comprend
    code = "ar" if lang in DIALECTES else lang[:2]
    try:
        echantillons = _decoder(audio)
        if len(echantillons) > DUREE_MAX_S * 16000:
            raise AudioInvalide("audio trop long")

        def lancer(langue):
            return modele(nom).transcribe(echantillons, language=langue, **OPTIONS,
                                          hotwords=vocabulaire() if langue in LANGUES_VOCABULAIRE else None)

        segments, info = lancer(code if code in LANGUES_WHISPER else None)
        probas = dict(info.all_language_probs or [])
        arabe = code == "ar" or info.language == "ar" or probas.get("ar", 0) >= PART_ARABE
        if arabe and nom is None and MODELE_ARABE != MODELE_STT:  # arabe, dialectes, tunisien mêlé de français
            segments, _ = modele(MODELE_ARABE).transcribe(echantillons, language="ar", **OPTIONS)
            texte = " ".join(s.text.strip() for s in segments).strip()
            return {"texte": texte, "langue": "ar", "confiance": round(max(probas.get("ar", 0), info.language_probability
                    if info.language == "ar" else 0), 2), "duree_audio_s": round(info.duration, 2),
                    "duree_s": round(time.time() - debut, 2)}
        # langue détectée : seulement parmi les nôtres (polonais... -> la plus probable des nôtres) ; détectée fr, en,
        # de ou tr : relancée avec les noms de lieux favorisés (le décodage n'a pas encore commencé : peu de coût)
        if info.language not in LANGUES_WHISPER or (code not in LANGUES_WHISPER and info.language in LANGUES_VOCABULAIRE):
            langue = info.language if info.language in LANGUES_WHISPER else \
                max(LANGUES_WHISPER, key=lambda l: probas.get(l, 0))
            segments, info = lancer(langue)
        if info.duration > DUREE_MAX_S:
            raise AudioInvalide("audio trop long")
        texte = " ".join(s.text.strip() for s in segments).strip()
    except AudioInvalide:
        raise
    except Exception as ex:  # noqa: BLE001  (format illisible)
        raise AudioInvalide(f"audio illisible ({type(ex).__name__})") from ex
    return {"texte": texte, "langue": info.language, "confiance": round(info.language_probability, 2),
            "duree_audio_s": round(info.duration, 2), "duree_s": round(time.time() - debut, 2)}
