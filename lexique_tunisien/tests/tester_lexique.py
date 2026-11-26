# -*- coding: utf-8 -*-
"""
Teste le lexique sur des questions (tests/questions_test.csv).

Usage :
    python tests/tester_lexique.py --dalila <dossier dalila_final dezippe>

Trois mesures :
 1. Detection : le message est-il reconnu comme du tunisien (et le francais / l'arabe standard NON) ?
 2. Concepts  : les mots de la question sont-ils relies aux bons concepts (terrain, prix, papiers...) ?
 3. Recherche : une recherche simple par mots-cles (BM25) dans les reponses de l'AFI trouve-t-elle
                le bon passage dans les 5 premiers, AVANT et APRES enrichissement par le lexique ?
On compare deux reglages : lexique "atteste" seulement, et lexique avec les formes "a valider".
"""
import argparse, collections, csv, json, math, os, re, sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
sys.path.insert(0, os.path.join(RACINE, "outils"))
from normaliser import NormaliseurTunisien, tokens  # noqa: E402

TYPES_POOL = {"reponse_validee_afi", "fiche_zone", "formulaire", "procedure"}
STOP = set("le la les de des du un une et a au aux en dans pour par sur est que qui quoi quel quelle ce il y l d".split())


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [[w for w in tokens(d) if w not in STOP] for d in docs]
        self.N = len(self.docs)
        self.avg = sum(map(len, self.docs)) / self.N
        self.df = collections.Counter(w for d in self.docs for w in set(d))
        self.tf = [collections.Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def top(self, q, k=5):
        qt = [w for w in tokens(q) if w not in STOP]
        sc = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            L = len(self.docs[i])
            for w in qt:
                if w in tf:
                    idf = math.log(1 + (self.N - self.df[w] + 0.5) / (self.df[w] + 0.5))
                    s += idf * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * L / self.avg))
            sc.append(s)
        return sorted(range(self.N), key=lambda i: -sc[i])[:k]


def bon(attendu, ids, textes):
    if not attendu:
        return None
    if attendu.startswith("ids:"):
        return any(i in attendu[4:].split(",") for i in ids)
    rx = re.compile(attendu[6:])
    return any(rx.search(t) for t in textes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dalila", required=True)
    a = ap.parse_args()
    pool = []
    with open(os.path.join(a.dalila, "6_pret_pour_le_llm", "passages.jsonl"), encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            if d["type"] in TYPES_POOL:
                pool.append(d)
    bm = BM25([d["titre"] + " " + d["texte"] for d in pool])
    Q = list(csv.DictReader(open(os.path.join(ICI, "questions_test.csv"), encoding="utf-8-sig")))

    reglages = {"atteste": NormaliseurTunisien(), "avec_a_valider": NormaliseurTunisien(inclure_a_valider=True)}
    lignes, resume = [], {}
    for nom, n in reglages.items():
        det_ok = conc_tot = conc_ok = 0
        rech = collections.Counter()
        for q in Q:
            r = n.analyser(q["question"])
            attendu_tn = q["langue_attendue"] == "tn"
            det_ok += r["tunisien"] == attendu_tn
            att = [c for c in q["concepts_attendus"].split(";") if c]
            conc_tot += len(att)
            conc_ok += sum(c in r["concepts"] for c in att)
            res = {}
            for mode, texte in (("brut", q["question"]), ("enrichi", r["requete_pour_rag"])):
                ids = [pool[i]["id"] for i in bm.top(texte)]
                txt = [pool[i]["titre"] + " " + pool[i]["texte"] for i in bm.top(texte)]
                res[mode] = bon(q["passages_attendus"], ids, txt)
                if res[mode] is not None:
                    rech[(mode, q["origine"].split(" ")[0])] += res[mode]
                    rech[(mode, "total")] += res[mode]
            lignes.append([nom, q["id"], q["origine"], q["question"], q["langue_attendue"], r["tunisien"],
                           ";".join(att), ";".join(r["concepts"]),
                           ";".join(c for c in att if c not in r["concepts"]),
                           res["brut"], res["enrichi"], r["en_arabe"]])
        nb_rech = sum(1 for q in Q if q["passages_attendus"])
        resume[nom] = dict(detection=f"{det_ok}/{len(Q)}", concepts=f"{conc_ok}/{conc_tot}",
                           recherche_brute=f"{rech[('brut', 'total')]}/{nb_rech}",
                           recherche_enrichie=f"{rech[('enrichi', 'total')]}/{nb_rech}")

    with open(os.path.join(ICI, "resultats_tests.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["reglage", "id", "origine", "question", "langue_attendue", "detecte_tunisien",
                    "concepts_attendus", "concepts_trouves", "concepts_manques",
                    "bon_passage_top5_sans_lexique", "bon_passage_top5_avec_lexique", "arabizi_en_lettres_arabes"])
        w.writerows(lignes)
    json.dump(resume, open(os.path.join(ICI, "resume_tests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(resume, ensure_ascii=False, indent=1))
    print(f"(recherche BM25 sur {len(pool)} passages : reponses validees AFI, fiches zones, formulaires, procedures)")


if __name__ == "__main__":
    main()
