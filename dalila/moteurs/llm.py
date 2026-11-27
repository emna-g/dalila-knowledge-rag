"""Modèle de langage local (Ollama), avec appels d'outils. Aucun service externe, aucune clé (BNF9).

    from dalila.moteurs.llm import discuter
    reponse = discuter(messages, outils=definitions())   # -> {"content": ..., "tool_calls": [...], "duree_s": ...}

Réglages (fichier .env) :
  DALILA_LLM            modèle Ollama (défaut : dalila-qwen3-4b, le modèle ajusté, s'il est installé ; sinon
                        qwen3:4b-instruct ; choix mesuré : docs/decisions.md)
  DALILA_LLM_URL        adresse d'Ollama (défaut : http://127.0.0.1:11434)
  DALILA_LLM_CPU        1 : processeur seulement, comme le serveur de l'AFI (pour mesurer) ; 0 (défaut) : carte graphique si là
  DALILA_LLM_FILS       nombre de fils de calcul (défaut 8, comme le serveur de l'AFI)
  DALILA_LLM_GABARIT    gabarit de conversation (jinja) avec lequel le modèle a été ajusté ; par défaut celui de
                        ajustement/gabarit_entrainement.jinja pour les modèles « dalila-* » ; vide : gabarit d'Ollama
Le mode « réflexion » des modèles Qwen3 est coupé : il allonge beaucoup les réponses sur processeur. La variante
« instruct » est celle qui le respecte (l'étiquette qwen3:4b désigne la variante « thinking », qui réfléchit toujours).

Modèle ajusté : il doit lire ses conversations EXACTEMENT comme à l'entraînement. Avec le gabarit d'Ollama, il répétait
ses appels d'outils au lieu de répondre ; avec le gabarit d'entraînement, il répond juste. La conversation est donc
écrite ici avec ce gabarit et envoyée brute à Ollama (/api/generate, raw), et les appels d'outils <tool_call> sont lus
ici. Le bloc vide qui précède ses réponses (<think></think> à l'entraînement, lu <tool_call></tool_call> après la
conversion en GGUF) est retiré : ce n'est ni une réponse, ni un appel.
"""
import json, os, re, time, urllib.request
from dalila.config import RACINE

URL = os.environ.get("DALILA_LLM_URL", "http://127.0.0.1:11434")
MODELE_AJUSTE, MODELE_BASE = "dalila-qwen3-4b", "qwen3:4b-instruct"


def _modele_par_defaut():
    """Le modèle ajusté s'il est installé dans Ollama (ajustement/Modelfile), sinon le modèle de base : le service
    démarre toujours. DALILA_LLM l'impose."""
    if os.environ.get("DALILA_LLM"):
        return os.environ["DALILA_LLM"]
    try:
        with urllib.request.urlopen(URL + "/api/tags", timeout=5) as r:
            noms = {m["name"].split(":latest")[0] for m in json.loads(r.read().decode("utf-8")).get("models", [])}
        return MODELE_AJUSTE if MODELE_AJUSTE in noms else MODELE_BASE
    except Exception:  # noqa: BLE001  (Ollama arrêté : l'erreur viendra à la première question, avec repli)
        return MODELE_BASE


MODELE_LLM = _modele_par_defaut()
GABARIT = os.environ.get("DALILA_LLM_GABARIT")

_REFLEXION = re.compile(r"<think>.*?(?:</think>|$)\s*", re.S)
_VIDE = re.compile(r"<tool_call>\s*</tool_call>\s*")
_APPEL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
_gabarits = {}
BLOC_VIDE = "<think>" + chr(10) * 2 + "</think>" + chr(10) * 2  # ouvre chaque réponse du modèle ajusté


def visible(texte):
    """Le texte sans bloc <think>…</think> ni appel vide (jamais montrés au visiteur, et ne comptent pas comme une
    réponse commencée)."""
    return _VIDE.sub("", _REFLEXION.sub("", texte or "")).strip()


class ErreurMoteur(Exception):
    """Le moteur ne répond pas (arrêté, trop lent) : le harnais répond quand même, en texte (BNF4)."""


def _gabarit(modele):
    chemin = GABARIT if GABARIT is not None else \
        (str(RACINE / "ajustement" / "gabarit_entrainement.jinja") if modele.startswith("dalila") else "")
    if not chemin:
        return None
    if chemin not in _gabarits:
        import jinja2
        env = jinja2.Environment(extensions=["jinja2.ext.loopcontrols"])
        env.filters["tojson"] = lambda x, **k: json.dumps(x, ensure_ascii=False)
        env.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(ValueError(m))
        _gabarits[chemin] = env.from_string(open(chemin, encoding="utf-8").read())
    return _gabarits[chemin]


def _lire_brut(texte):
    """Sortie brute du modèle ajusté -> (texte de réponse, appels d'outils)."""
    appels = []
    for bloc in _APPEL.findall(texte):
        try:
            a = json.loads(bloc)
            appels.append({"function": {"name": a["name"], "arguments": a.get("arguments") or {}}})
        except (ValueError, KeyError):
            continue
    return visible(_APPEL.sub("", texte)), appels


def _texte_commence(brut):
    """Vrai si le modèle écrit une réponse (pas un appel d'outil, ni le début d'une balise encore incomplète)."""
    reste = visible(_APPEL.sub("", brut))
    if not reste:
        return False
    return not ("<tool_call>".startswith(reste) or reste.startswith("<tool_call>") or "<tool_call>".startswith(reste[:11]))


def discuter(messages, outils=None, modele=None, delai_s=60, temperature=0.0, jetons_max=400, arret_si_texte=False,
             reponse_attendue=False):
    """jetons_max : borne de ce que le modèle écrit (≈ 5 jetons/s sur le processeur du serveur de l'AFI).

    arret_si_texte : le modèle doit appeler un outil ; s'il commence à écrire du texte, la génération est arrêtée tout
    de suite (lecture en flux, connexion fermée) et le résultat porte "interrompu": True. Coût : une seconde environ,
    au lieu d'une réponse entière écrite sans données.
    reponse_attendue : les outils ont rendu leurs résultats, le modèle écrit sa réponse. Pour le modèle ajusté, le bloc
    vide <think></think> qui ouvrait chaque réponse à l'entraînement est écrit d'avance : sans lui, il le régénère sous
    une autre forme et tourne en rond (mesuré : réponses justes avec, boucles sans).
    Rend {content, tool_calls, duree_s, jetons_lus, jetons_ecrits, fin ("stop" ou "length"), interrompu}.
    """
    modele = modele or MODELE_LLM
    options = {"temperature": temperature, "num_ctx": 8192, "num_predict": jetons_max}
    if os.environ.get("DALILA_LLM_CPU", "0") == "1":
        options.update({"num_gpu": 0, "num_thread": int(os.environ.get("DALILA_LLM_FILS", "8"))})
    gabarit = _gabarit(modele)
    if gabarit is not None:  # modèle ajusté : conversation écrite avec le gabarit d'entraînement, envoyée brute
        options["stop"] = ["<|im_end|>", "<|im_start|>"]
        prompt = gabarit.render(messages=[{k: v for k, v in m.items() if k != "tool_name"} for m in messages],
                                tools=outils or None, add_generation_prompt=True, bos_token="", eos_token="")
        if reponse_attendue:
            prompt += BLOC_VIDE
        corps = {"model": modele, "prompt": prompt, "raw": True, "stream": arret_si_texte, "options": options,
                 "keep_alive": "30m"}
        chemin = "/api/generate"
    else:
        corps = {"model": modele, "messages": messages, "stream": arret_si_texte, "think": False,
                 "options": options, "keep_alive": "30m"}
        if outils:
            corps["tools"] = outils
        chemin = "/api/chat"
    req = urllib.request.Request(URL + chemin, data=json.dumps(corps).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    debut = time.time()
    contenu, appels, fin, interrompu = "", [], {}, False
    try:
        with urllib.request.urlopen(req, timeout=delai_s) as r:
            if not arret_si_texte:
                fin = json.loads(r.read().decode("utf-8"))
                if gabarit is not None:
                    contenu = fin.get("response") or ""
                else:
                    m = fin.get("message", {})
                    contenu, appels = m.get("content") or "", m.get("tool_calls") or []
            else:
                for ligne in r:
                    morceau = json.loads(ligne.decode("utf-8"))
                    if gabarit is not None:
                        contenu += morceau.get("response") or ""
                        commence = _texte_commence(contenu)
                    else:
                        m = morceau.get("message", {})
                        contenu += m.get("content") or ""
                        appels += m.get("tool_calls") or []
                        commence = bool(visible(contenu)) and not appels
                    if commence:
                        interrompu = True  # fermer la connexion arrête la génération dans Ollama
                        break
                    if morceau.get("done"):
                        fin = morceau
                        break
    except Exception as ex:  # noqa: BLE001
        raise ErreurMoteur(f"{type(ex).__name__}: {ex}") from ex
    if gabarit is not None:
        contenu, appels = _lire_brut(contenu)
    return {"content": visible(contenu), "duree_s": round(time.time() - debut, 2), "interrompu": interrompu,
            "tool_calls": [{"nom": c["function"]["name"], "arguments": c["function"].get("arguments") or {}}
                           for c in appels],
            "jetons_lus": fin.get("prompt_eval_count"), "jetons_ecrits": fin.get("eval_count"),
            "fin": fin.get("done_reason")}
