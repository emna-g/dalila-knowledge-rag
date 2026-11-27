"""Mesure la vitesse des modèles de recherche SUR PROCESSEUR (le serveur de l'AFI n'a pas de carte graphique).

python -m eval.vitesse_cpu                     e5, bge, qwen3 + reranker
python -m eval.vitesse_cpu --fils 8            comme le serveur de l'AFI (8 vCPU)

Les vecteurs des passages sont calculés une fois, hors ligne (carte graphique). À chaque question, il reste à :
encoder la question (un modèle), et, si le reranker est actif, relire les 20 meilleurs passages.
Résultat : eval/reports/vitesse_cpu.json (médiane et 95e centile, en millisecondes).
"""
import argparse, csv, json, statistics, time
from dalila.config import MODELES_RECHERCHE, NOM_RERANKER, RACINE, db


def mesure(f, n):
    t = []
    for _ in range(n):
        d = time.perf_counter()
        f()
        t.append((time.perf_counter() - d) * 1000)
    t.sort()
    return {"mediane_ms": round(statistics.median(t)), "p95_ms": round(t[max(0, int(0.95 * len(t)) - 1)])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modeles", nargs="+", default=list(MODELES_RECHERCHE))
    ap.add_argument("--fils", type=int, default=8, help="nombre de fils de calcul (le serveur de l'AFI : 8 vCPU)")
    a = ap.parse_args()
    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer
    torch.set_num_threads(a.fils)
    questions = [r["question"] for r in csv.DictReader(
        open(RACINE / "eval/testset/questions_reelles.csv", encoding="utf-8-sig"))][:20]
    with db("root").cursor() as cur:
        cur.execute("SELECT texte FROM dalila_passages WHERE pertinence = 'principale' ORDER BY id LIMIT 20")
        passages = [r["texte"][:1500] for r in cur.fetchall()]
    res = {"fils": a.fils}
    for m in a.modeles:
        cfg = MODELES_RECHERCHE[m]
        mod = SentenceTransformer(cfg["nom"], device="cpu")
        i = iter(questions * 5)
        mod.encode([cfg["prefixe_question"] + questions[0]])  # chauffe
        res[m] = mesure(lambda: mod.encode([cfg["prefixe_question"] + next(i)], normalize_embeddings=True), 20)
        print(m, res[m], flush=True)
        del mod
    rr = CrossEncoder(NOM_RERANKER, device="cpu", max_length=512)
    rr.predict([(questions[0], passages[0])])
    i = iter(questions * 5)
    res["reranker_20_passages"] = mesure(lambda: rr.predict([(next(i), p) for p in passages]), 5)
    print("reranker (20 passages)", res["reranker_20_passages"], flush=True)
    out = RACINE / "eval/reports/vitesse_cpu.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
