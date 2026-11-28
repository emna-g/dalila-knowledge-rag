"""Langue du visiteur parmi les 6 retenues (BF1), par des modèles, sans règle écrite à la main.

    from dalila.langue.detection import detecter
    detecter("n7eb terrain f Sfax") -> {"langue": "tn", "ecriture": "latin", "confiance": 0.9}

Langues retenues (décision de l'équipe, 2026-11-28) : fr, en, ar (arabe standard), de, tr, tn (tunisien, en lettres
arabes ou en arabizi). L'algérien et le libyen ne sont plus proposés.
- Lettres arabes : CAMeL-Lab/bert-base-arabic-camelbert-mix-did-madar-corpus26 (Apache 2.0) distingue 25 villes et
  l'arabe standard. Tunis et Sfax -> tunisien ; Alger, Tripoli et Benghazi -> tunisien aussi : la variété proche que
  Dalila parle, et le modèle confond souvent ces voisins (un message tunisien du lexique était lu « Alger ») ; arabe
  standard et autres villes (Caire, Beyrouth...) -> ar.
- Lettres latines : classifieur de n-grammes de caractères (dalila/langue/entrainer_detection.py) : fr, en, de, tr,
  tunisien en arabizi ; sa classe « arabizi algérien » est rendue comme tunisien, pour la même raison.
Codes rendus, ceux du contrat /carte/chatbot : fr, en, ar, de, tr, tn. L'écriture (arabe, latine) est lue sur les
lettres elles-mêmes (propriété Unicode). Mesure : python -m dalila.langue.detection --mesurer ->
eval/reports/detection_langue.json.
"""
import argparse, collections, csv, json, sys, threading
from dalila.config import LEXIQUE, MODELES, RACINE

MADAR = "CAMeL-Lab/bert-base-arabic-camelbert-mix-did-madar-corpus26"
# codes rendus : fr, en, ar, de, tr, tn (algérien et libyen abandonnés : rendus comme la variété voisine, le tunisien)
VILLES = {"TUN": "tn", "SFX": "tn", "ALG": "tn", "TRI": "tn", "BEN": "tn", "MSA": "ar"}
CONTRAT = {"aeb": "tn", "arq": "tn"}  # classes du classifieur (codes ISO) -> codes du contrat
CODES_JEUX = {}
_m, _verrou = {}, threading.Lock()


def ecriture(texte):
    lettres = [c for c in texte if c.isalpha()]
    if not lettres:
        return "aucune"
    arabe = sum("؀" <= c <= "ۿ" for c in lettres) / len(lettres)
    return "arabe" if arabe >= 0.5 else "latin"


def _modeles():
    with _verrou:
        if not _m:
            import joblib
            from transformers import pipeline
            _m["latin"] = joblib.load(MODELES / "langue_latin.joblib")
            _m["arabe"] = pipeline("text-classification", model=MADAR, device=-1, model_kwargs={"cache_dir": str(MODELES)})
        return _m


def detecter(texte):
    texte = (texte or "").strip()
    e = ecriture(texte)
    if e == "aucune":
        return {"langue": None, "ecriture": e, "confiance": 0.0}
    m = _modeles()
    if e == "arabe":
        r = m["arabe"](texte[:512])[0]
        return {"langue": VILLES.get(r["label"], "ar"), "ecriture": e, "confiance": round(r["score"], 2),
                "variete": r["label"]}
    p = m["latin"].predict_proba([texte])[0]
    i = p.argmax()
    classe = str(m["latin"].classes_[i])
    return {"langue": CONTRAT.get(classe, classe), "ecriture": e, "confiance": round(float(p[i]), 2)}


def mesurer():
    jeux = {"6 langues": (RACINE / "eval/testset/questions_claude_a_relire.csv", "langue"),
            "vraies questions": (RACINE / "eval/testset/questions_reelles.csv", "langue"),
            "lexique tunisien": (LEXIQUE / "tests/questions_test.csv", "langue_attendue")}
    rapport = {}
    for nom, (f, col) in jeux.items():
        ok, n, par, erreurs = 0, 0, collections.defaultdict(lambda: [0, 0]), []
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            attendu = CODES_JEUX.get(r[col], r[col])
            if not attendu:
                continue
            d = detecter(r["question"])["langue"]
            n += 1
            ok += d == attendu
            par[attendu][0] += d == attendu
            par[attendu][1] += 1
            if d != attendu and len(erreurs) < 8:
                erreurs.append(f"{attendu} -> {d} : {r['question'][:60]}")
        rapport[nom] = {"justes": f"{ok}/{n}", "par_langue": {k: f"{a}/{b}" for k, (a, b) in sorted(par.items())},
                        "exemples_d_erreurs": erreurs}
    (RACINE / "eval/reports/detection_langue.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1),
                                                                encoding="utf-8")
    return rapport


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesurer", action="store_true")
    ap.add_argument("texte", nargs="?")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(mesurer() if a.mesurer else detecter(a.texte), ensure_ascii=False, indent=1))
