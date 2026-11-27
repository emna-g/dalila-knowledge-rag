"""Conversations réussies -> exemples d'entraînement pour le prochain ajustement de l'agent (BF18, BNF17).

    .venv\\Scripts\\python -m dalila.apprentissage.exporter          -> donnees/ajustement/reel.jsonl
    .venv\\Scripts\\python -m ajustement.generer --enseignant --reel  -> jeu d'entraînement avec ces exemples

Un tour journalisé devient un exemple seulement s'il passe tous ces contrôles :
- Dalila a répondu (pas de repli), le visiteur ne l'a pas noté « pas utile », la réponse du modèle est journalisée ;
- les outils sont rappelés AUJOURD'HUI avec les mêmes arguments, sans erreur, et chaque nombre de la réponse se trouve
  encore dans leurs résultats (une réponse devenue fausse, par exemple après un changement de prix, est écartée) ;
- pas de lieu rattrapé par le harnais (le modèle n'a pas su le recopier : mauvais exemple) ; pas de réponse en boucle ;
- jamais une question du jeu de test (eval/testset), pour que le gain mesuré reste vrai ;
- textes déjà anonymisés au journal, masqués une seconde fois.
L'exemple a la forme exacte des conversations de service (consignes, outils, résultats, rappel de langue).
"""
import csv, json, re, sys
from dalila.config import DONNEES, RACINE, db
from dalila.harnais.agent import CONSIGNE_HORS_SUJET, degenere
from dalila.harnais.consignes import RAPPEL_LANGUE, systeme
from dalila.harnais.garde_fous import masquer, verifier_ancrage
from dalila.harnais.vues import vue
from dalila.traitement.registre import appeler

SORTIE = DONNEES / "ajustement" / "reel.jsonl"


def _norm(t):
    return re.sub(r"\W+", " ", (t or "").lower()).strip()


def _questions_test():
    with open(RACINE / "eval/testset/questions_reelles.csv", encoding="utf-8-sig") as f:
        return {_norm(r["question"]) for r in csv.DictReader(f)}


def _tours():
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute("SELECT id, texte_anonymise, langue, outils, reponse, avis FROM agent_turns "
                        "WHERE source = 'dalila' AND reponse IS NOT NULL AND reponse <> '' "
                        "AND (avis IS NULL OR avis = 1) ORDER BY id")
            return cur.fetchall()
    finally:
        con.close()


def exemple(tour, test=frozenset()):
    """-> (exemple, None) ou (None, raison du rejet)"""
    question, reponse = masquer(tour["texte_anonymise"] or ""), masquer(tour["reponse"] or "")
    if not question or not reponse:
        return None, "vide"
    if _norm(question) in test:
        return None, "question du jeu de test"
    if degenere(reponse):
        return None, "réponse en boucle"
    appels = [o for o in json.loads(tour["outils"] or "[]") if not str(o.get("outil", "")).startswith("(")]
    if not appels:
        return None, "aucun outil"
    if any(o.get("arguments_modele") for o in appels):
        return None, "lieu rattrapé par le harnais"
    messages, resultats = [systeme(), {"role": "user", "content": question}], []
    for o in appels:
        nom, args = o["outil"], o.get("arguments") or {}
        res = CONSIGNE_HORS_SUJET if nom == "hors_sujet" else appeler(nom, args)
        if "erreur" in res:
            return None, f"outil en erreur aujourd'hui ({nom})"
        if nom != "hors_sujet":
            resultats.append(res)
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": nom, "arguments": dict(sorted(args.items()))}}]})
        messages.append({"role": "tool", "name": nom, "content": vue(nom, res)})
    if not verifier_ancrage(reponse, resultats, question)["ok"]:
        return None, "nombres plus justes avec les données d'aujourd'hui"
    messages.append({"role": "user", "content": RAPPEL_LANGUE.format(message=question[:200], interface="")})
    messages.append({"role": "assistant", "content": reponse})
    return {"langue": tour["langue"] or "?", "outil": appels[-1]["outil"], "source": f"agent_turns/{tour['id']}",
            "messages": messages}, None


def exporter(sortie=SORTIE):
    test, vus, gardes, rejets = _questions_test(), set(), [], {}
    for t in _tours():
        cle = _norm(t["texte_anonymise"])
        if cle in vus:
            rejets["déjà exportée"] = rejets.get("déjà exportée", 0) + 1
            continue
        ex, raison = exemple(t, test)
        if ex:
            vus.add(cle)
            gardes.append(ex)
        else:
            rejets[raison] = rejets.get(raison, 0) + 1
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as f:
        for e in gardes:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(gardes), rejets


def main():
    n, rejets = exporter()
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{n} exemples écrits dans {SORTIE} ; écartés : {rejets}")


if __name__ == "__main__":
    main()
