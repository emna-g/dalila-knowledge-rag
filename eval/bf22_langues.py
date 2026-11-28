"""Test d'acceptation BF22 dans les 6 langues retenues (tunisien en arabizi et en lettres arabes) :
« La banque me demande un papier pour mon prêt » mène, éventuellement après une question à choix, à l'attestation
d'insertion d'hypothèque.

    .venv\\Scripts\\python -m eval.bf22_langues        (processeur seul, comme le serveur de l'AFI)

Réussi si l'agent appelle demarche(service="insertion_hypotheque"), ou pose une question à choix dont une option est
ce service (« Obtenir un prêt bancaire »). Rapport : eval/reports/bf22_langues.json.
"""
import json, os, sys
os.environ.setdefault("DALILA_LLM_CPU", "1")
from dalila.config import RACINE
from dalila.harnais.agent import Agent

QUESTIONS = {
    "fr": "La banque me demande un papier pour mon prêt",
    "en": "The bank is asking me for a document for my loan",
    "ar": "البنك يطلب مني وثيقة من أجل القرض",
    "de": "Die Bank verlangt von mir ein Dokument für meinen Kredit",
    "tr": "Banka kredim için benden bir belge istiyor",
    "tn (arabizi)": "el banka tlabet menni war9a 3al crédit mte3i",
    "tn (lettres arabes)": "البنكة طلبت مني ورقة على الكريدي متاعي",
}


def reussi(r):
    if any(o["outil"] == "demarche" and (o.get("arguments") or {}).get("service") == "insertion_hypotheque"
           for o in r["outils"]):
        return "service trouvé"
    if "[[CHOIX:" in r["reponse"] and "prêt bancaire" in r["reponse"]:
        return "question à choix (le service est une option)"
    return None


def main():
    a = Agent()
    a.prechauffer()
    lignes = []
    for lang, q in QUESTIONS.items():
        r = a.repondre(q)
        ok = reussi(r)
        lignes.append({"langue": lang, "question": q, "reussi": bool(ok), "comment": ok, "duree_s": r["duree_s"],
                       "outils": [(o["outil"], o.get("arguments")) for o in r["outils"]], "reponse": r["reponse"][:300]})
        print(f"  {lang:20s} {r['duree_s']:5.1f}s {'OK ' if ok else 'NON'} {ok or ''} | {[o['outil'] for o in r['outils']]}",
              flush=True)
    resume = {"reussis": f"{sum(l['reussi'] for l in lignes)}/{len(lignes)}", "modele": a.modele, "details": lignes}
    (RACINE / "eval/reports/bf22_langues.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("réussis :", resume["reussis"])


if __name__ == "__main__":
    main()
