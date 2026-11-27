"""Entraîne le classifieur de langue des messages en lettres latines (BF1) ; une fois, quelques minutes.

    .venv\\Scripts\\python -m dalila.langue.entrainer_detection      -> modeles/langue_latin.joblib

Classes : fr, en, de, tr, aeb (tunisien en arabizi), arq (algérien en arabizi). Données ouvertes :
- papluca/language-identification (MIT) : phrases fr, en, de, tr ;
- arbml/TUNIZI : commentaires tunisiens en arabizi ;
- touati-kamel/Algerian-Youtube-Comments (MIT) : commentaires algériens ; pour la classe « algérien en arabizi »,
  seulement ceux en lettres latines qui contiennent un mot à chiffre-lettre (« mou7tawa ») : beaucoup sont en français.
  Ce filtre sert seulement à préparer les données ; le classifieur, lui, n'a aucune règle écrite.
Modèle : n-grammes de caractères (1 à 4) et régression logistique : la forme des mots, pas leur sens.
Les questions des jeux de test (eval/testset, lexique/tests) ne servent jamais ici.
"""
import csv, json, random, re, sys, urllib.request
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from dalila.config import MODELES

SORTIE = MODELES / "langue_latin.joblib"
PAR_CLASSE = 3000


def _lignes(ds, cfg, split, n, champ, saut=0):
    out = []
    for debut in range(saut, saut + n, 100):
        u = f"https://datasets-server.huggingface.co/rows?dataset={ds}&config={cfg}&split={split}&offset={debut}&length=100"
        try:
            rows = json.load(urllib.request.urlopen(u, timeout=60))["rows"]
        except Exception:  # noqa: BLE001
            break
        out += [r["row"].get(champ) or "" for r in rows]
        if len(rows) < 100:
            break
    return [t for t in out if t and t.strip()]


def _latin(t):
    lettres = [c for c in t if c.isalpha()]
    return lettres and sum(c.isascii() for c in lettres) / len(lettres) > 0.9


def donnees():
    from huggingface_hub import hf_hub_download
    import csv
    X, y = [], []
    f = hf_hub_download("papluca/language-identification", "train.csv", repo_type="dataset", cache_dir=str(MODELES))
    par = {}
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if r["labels"] in ("fr", "en", "de", "tr"):
            par.setdefault(r["labels"], []).append(r["text"])
    for lang, textes in par.items():
        random.Random(7).shuffle(textes)
        X += textes[:PAR_CLASSE]; y += [lang] * len(textes[:PAR_CLASSE])
    tn = [t for t in _lignes("arbml/TUNIZI", "default", "train", 4000, "text") if _latin(t)]
    X += tn[:PAR_CLASSE]; y += ["aeb"] * len(tn[:PAR_CLASSE])
    dz = []
    for saut in range(0, 40000, 4000):
        dz += [t for t in _lignes("touati-kamel/Algerian-Youtube-Comments", "default", "train", 1500, "comment_text", saut)
               if _latin(t) and re.search(r"[a-z][2-9][a-z]|\b[379][a-z]", t.lower())]
        if len(dz) >= PAR_CLASSE:
            break
    X += dz[:PAR_CLASSE]; y += ["arq"] * len(dz[:PAR_CLASSE])
    # questions du domaine, dans chaque langue : les noms de lieux (Sfax, Jendouba...) et le style des visiteurs ne
    # doivent pas désigner une langue à eux seuls
    Xd, yd = questions_du_domaine()
    for _ in range(3):  # peu nombreuses : comptées trois fois
        X += Xd; y += yd
    return X, y


def _norm(t):
    return re.sub(r"\W+", " ", (t or "").lower()).strip()


def questions_du_domaine():
    """Vraies questions de l'ancien chatbot (chatbot_logs, langue enregistrée ; jamais celles du jeu de test) et
    questions du jeu d'ajustement, en lettres latines."""
    from dalila.config import DONNEES, LEXIQUE, RACINE, db
    from dalila.harnais.garde_fous import masquer

    def q(sql):  # étape de construction (comme dalila.connaissances.charger) : compte de construction, textes masqués
        con = db("root")
        try:
            with con.cursor() as cur:
                cur.execute(sql)
                return [{**r, "question": masquer(r["question"] or "")} for r in cur.fetchall()]
        finally:
            con.close()
    test = set()
    for f, col in ((RACINE / "eval/testset/questions_reelles.csv", "question"),
                   (RACINE / "eval/testset/questions_claude_a_relire.csv", "question"),
                   (LEXIQUE / "tests/questions_test.csv", "question")):
        test |= {_norm(r[col]) for r in csv.DictReader(open(f, encoding="utf-8-sig"))}
    X, y = [], []
    try:
        for r in q("SELECT question, lang FROM chatbot_logs"):
            if r["lang"] in ("fr", "en") and _latin(r["question"] or "") and _norm(r["question"]) not in test:
                X.append(r["question"]); y.append(r["lang"])
    except Exception:  # noqa: BLE001  (compte sans accès à chatbot_logs : seulement le jeu d'ajustement)
        pass
    codes = {"fr": "fr", "en": "en", "de": "de", "tr": "tr", "aeb_lat": "aeb", "arq_lat": "arq"}
    f = DONNEES / "ajustement" / "train.jsonl"
    if f.exists():
        for l in open(f, encoding="utf-8"):
            e = json.loads(l)
            texte = e["messages"][1]["content"]
            if e["langue"] in codes and _norm(texte) not in test:
                X.append(texte); y.append(codes[e["langue"]])
    return X, y


def main():
    X, y = donnees()
    sys.stdout.reconfigure(encoding="utf-8")
    print({c: y.count(c) for c in sorted(set(y))})
    m = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 4), min_df=2, sublinear_tf=True, lowercase=True),
                      LogisticRegression(max_iter=3000, C=4, class_weight="balanced"))
    m.fit(X, y)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, SORTIE)
    print("écrit :", SORTIE)


if __name__ == "__main__":
    main()
