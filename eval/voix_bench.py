"""Mesure de la voix (BNF3 : reconnaissance en 4 s au plus ; BF7, BF8), sur processeur.

    .venv\\Scripts\\python -m eval.voix_bench [--modeles small large-v3-turbo] [--dossier enregistrements/]

Sans dossier : chaque question est lue par la voix Piper de sa langue, puis reconnue par Whisper ; mesure surtout la
VITESSE (une voix de synthèse, sans bruit, est plus facile qu'un visiteur). Avec un dossier de vrais enregistrements
(<langue>_<n>.wav|webm|ogg|mp3 et <langue>_<n>.txt pour le texte attendu), mesure aussi l'exactitude réelle, dialectes
compris. Rapport : eval/reports/voix_resume.json.
"""
import argparse, difflib, json, os, pathlib, re, statistics, time
os.environ.setdefault("DALILA_LLM_FILS", "8")
from dalila.config import RACINE
from dalila.voix import reconnaissance, synthese

QUESTIONS = {
    "fr": "Je cherche un lot industriel de deux mille mètres carrés à Jendouba.",
    "en": "I am looking for an industrial lot near the port of Sfax.",
    "de": "Ich suche ein Industriegrundstück in Sousse.",
    "tr": "Bizerte'de sanayi arsası var mı?",
    "ar": "أبحث عن مقسم صناعي في ولاية القصرين.",
}
REPONSE = "7 lots disponibles à Jendouba. Le moins cher : 2 904 m² à 32 DT/m², soit 92 928 DT.\n\n- [[LOT:5200:A30]] Jendouba El IRTIYEH · 2 904 m²"


def _norm(t):
    return re.sub(r"[^\w\s]", "", t.lower()).split()


def exactitude(attendu, obtenu):
    """1 - taux d'erreur sur les mots (approché par l'alignement de difflib)."""
    a, o = _norm(attendu), _norm(obtenu)
    return round(difflib.SequenceMatcher(None, a, o).ratio(), 2) if a else None


def cas(dossier):
    if not dossier:
        for lang, q in QUESTIONS.items():
            t = time.time()
            audio = synthese.lire(q, lang)
            yield lang, q, audio, round(time.time() - t, 2)
        return
    for f in sorted(pathlib.Path(dossier).iterdir()):
        if f.suffix.lower() in (".wav", ".webm", ".ogg", ".mp3", ".m4a"):
            txt = f.with_suffix(".txt")
            yield f.stem.split("_")[0], txt.read_text(encoding="utf-8").strip() if txt.exists() else "", f.read_bytes(), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modeles", nargs="+", default=["small", "large-v3-turbo"])
    ap.add_argument("--dossier")
    a = ap.parse_args()
    jeu = list(cas(a.dossier))
    resume = {"materiel": "CPU 8 fils", "source_audio": a.dossier or "voix de synthèse Piper", "synthese": {}, "reconnaissance": {}}
    t = time.time()
    synthese.lire(REPONSE, "fr")  # chargement de la voix, non compté
    t = time.time()
    wav = synthese.lire(REPONSE, "fr")
    resume["synthese"]["reponse_fr_s"] = round(time.time() - t, 2)
    resume["synthese"]["reponse_fr_audio_s"] = round((len(wav) - 44) / 2 / 22050, 2)
    resume["synthese"]["par_langue_s"] = {lang: d for lang, _, _, d in jeu if d is not None}
    for nom in a.modeles:
        reconnaissance.transcrire(jeu[0][2], nom=nom)  # chargement du modèle, non compté
        lignes = []
        for lang, attendu, audio, _ in jeu:
            r = reconnaissance.transcrire(audio, nom=nom)  # sans indice de langue : la détection est mesurée aussi
            lignes.append({"langue": lang, "detectee": r["langue"], "duree_s": r["duree_s"], "audio_s": r["duree_audio_s"],
                           "exactitude": exactitude(attendu, r["texte"]), "texte": r["texte"]})
            print(f"  {nom:15s} {lang} {r['duree_s']:5.2f}s (audio {r['duree_audio_s']}s) détectée={r['langue']} "
                  f"exactitude={lignes[-1]['exactitude']} | {r['texte']}", flush=True)
        d = [l["duree_s"] for l in lignes]
        resume["reconnaissance"][nom] = {
            "duree_mediane_s": round(statistics.median(d), 2), "duree_max_s": max(d),
            "au_dela_4s": sum(x > 4 for x in d), "langue_ok": f"{sum(l['detectee'] == l['langue'][:2] for l in lignes)}/{len(lignes)}",
            "exactitude_moyenne": round(statistics.mean(l["exactitude"] for l in lignes if l["exactitude"] is not None), 2),
            "details": lignes}
    (RACINE / "eval" / "reports" / "voix_resume.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in resume.items() if k != "reconnaissance"}, ensure_ascii=False, indent=1))
    print(json.dumps({n: {k: v for k, v in x.items() if k != "details"} for n, x in resume["reconnaissance"].items()}, indent=1))


if __name__ == "__main__":
    main()
