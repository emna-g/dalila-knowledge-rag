"""Recherche dans les passages de Dalila : lexique tunisien + recherche hybride (sens + mots-clés).

    from rechercher import Recherche
    r = Recherche()
    r.chercher("chnowa lwra9 lazmin bech na5ou ma9sem sina3i?", k=5)

ou en ligne de commande :  python rechercher.py "n7eb terrain f Sfax"

Étapes :
1) Lexique : si le message est en tunisien (lettres arabes ou arabizi), le normaliseur ajoute les mots
   équivalents en français et en arabe standard. Une question déjà en français, arabe ou anglais n'est pas modifiée.
2) Deux recherches en parallèle :
   - par le SENS : la question devient un embedding (modèle e5) et ChromaDB renvoie les passages proches ;
   - par les MOTS-CLÉS (BM25) : utile pour les noms propres et les mots rares (« Sfax », « sardine »).
3) Fusion des deux classements (Reciprocal Rank Fusion : un passage bien placé dans les deux listes passe devant).
4) Variété : au plus 2 passages d'une même page.
5) Filtres de qualité : on écarte les passages « secondaires » et les passages très courts (mentions légales,
   menus), et on donne un petit bonus aux réponses validées par l'AFI, fiches de zone, formulaires et procédures.
"""
import collections, json, math, os, pathlib, re, sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI / "libs"))
os.environ.setdefault("HF_HOME", str(ICI / "modeles"))
LEXIQUE = pathlib.Path(os.environ.get("DALILA_LEXIQUE", ICI / "lexique_tunisien"))
DONNEES = pathlib.Path(os.environ.get("DALILA_DONNEES", ICI / "donnees" / "dalila_fusion"))
sys.path.insert(0, str(LEXIQUE / "outils"))
import chromadb  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from normaliser import NormaliseurTunisien, tokens  # noqa: E402

PRIORITAIRES = {"reponse_validee_afi": 1.0, "fiche_zone": 1.0, "formulaire": 0.6, "procedure": 0.6}
STOP = set("le la les de des du un une et a au aux en dans pour par sur est que qui quoi quel quelle ce il y l d "
           "the of to in and is what how في من على الى إلى و ما".split())
LONGUEUR_MIN = 200


class BM25:
    """Recherche par mots-clés classique (Okapi BM25)."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.tf = [collections.Counter(w for w in tokens(d) if w not in STOP) for d in docs]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        df = collections.Counter(w for t in self.tf for w in t)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def top(self, q, k=50):
        qt = [w for w in tokens(q) if w not in STOP and w in self.idf]
        sc = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in qt:
                f = tf.get(w)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s:
                sc.append((s, i))
        return [i for _, i in sorted(sc, reverse=True)[:k]]


class Recherche:
    def __init__(self, index=str(ICI / "index_chroma"), modele="intfloat/multilingual-e5-small", lexique=True,
                 hybride=True, filtres=True):
        self.modele = SentenceTransformer(modele, device="cpu")
        self.col = chromadb.PersistentClient(path=index).get_collection("passages_dalila")
        self.norm = NormaliseurTunisien() if lexique else None
        self.hybride, self.filtres = hybride, filtres
        P = [json.loads(l) for l in open(DONNEES / "6_pret_pour_le_llm/passages.jsonl", encoding="utf-8")]
        self.P = [p for p in P if p.get("a_indexer")]
        self.pos = {p["id"]: i for i, p in enumerate(self.P)}
        self.bm25 = BM25([f"{p.get('titre') or ''} {p['texte']}" for p in self.P]) if hybride else None

    def requete(self, question):
        if self.norm is None:
            return question, False
        r = self.norm.analyser(question)
        return r["requete_pour_rag"], r["tunisien"]

    def _garde(self, p):
        if not self.filtres:
            return True
        return p.get("pertinence") != "secondaire" and len(p["texte"]) >= LONGUEUR_MIN

    def chercher(self, question, k=5, profondeur=60):
        q, tn = self.requete(question)
        v = self.modele.encode(["query: " + q], normalize_embeddings=True).tolist()
        res = self.col.query(query_embeddings=v, n_results=profondeur)
        sens = [i for i in res["ids"][0] if self._garde(self.P[self.pos[i]])]
        sim = dict(zip(res["ids"][0], [1 - d for d in res["distances"][0]]))
        score = collections.defaultdict(float)
        for r, i in enumerate(sens):
            score[i] += 1 / (60 + r)  # Reciprocal Rank Fusion
        if self.bm25 is not None:
            mots = [self.P[j]["id"] for j in self.bm25.top(q, profondeur) if self._garde(self.P[j])]
            for r, i in enumerate(mots):
                score[i] += 1 / (60 + r)
        if self.filtres:
            for i in score:
                score[i] += PRIORITAIRES.get(self.P[self.pos[i]]["type"], 0) * 0.005
        out, par_source = [], collections.Counter()
        for i in sorted(score, key=score.get, reverse=True):
            if len(out) == k:
                break
            p = self.P[self.pos[i]]
            page = p.get("source_url") if str(p.get("source_url", "")).startswith("http") else i
            if self.filtres and par_source[page] >= 2:  # au plus 2 passages d'une même page web ou d'un même PDF
                continue
            par_source[page] += 1
            out.append({"id": i, "score": round(score[i], 4), "similarite": round(sim.get(i, 0), 3), "type": p["type"],
                        "titre": p.get("titre"), "source_url": p.get("source_url"), "date_source": p.get("date_source"),
                        "zone_id": p.get("zone_id"), "article": p.get("article"),
                        "texte_ocr": bool(p.get("texte_ocr")), "contient_chiffre": bool(p.get("contient_chiffre")),
                        "texte": p["texte"]})
        return {"question": question, "tunisien": tn, "requete": q, "resultats": out}


if __name__ == "__main__":
    r = Recherche()
    res = r.chercher(" ".join(sys.argv[1:]) or "n7eb terrain f Sfax")
    print("tunisien :", res["tunisien"], "| requête :", res["requete"][:150])
    for x in res["resultats"]:
        print(f"{x['score']:.4f}  {x['id']}  [{x['type']}] {(x['titre'] or '')[:70]}  <{(x['source_url'] or '')[:60]}>")
