"""Apprentissage contrôlé des synonymes : un mot des visiteurs -> une activité de l'ontologie (BF18, BF19, BF21, BNF15 à
BNF18).

    .venv\\Scripts\\python -m dalila.apprentissage.synonymes_appris              cycle complet
    .venv\\Scripts\\python -m dalila.apprentissage.synonymes_appris --lister
    .venv\\Scripts\\python -m dalila.apprentissage.synonymes_appris --annuler 3

Exemple : des visiteurs écrivent « 3andi projet sardine » ; l'agent reformule (« conserverie de poisson ») et l'outil
conseiller trouve l'activité « Transformation et conservation de poisson ». Le mot « sardine », lui, n'y menait pas.
Après au moins SESSIONS_MIN conversations distinctes, toujours vers la même activité, et les contrôles, « sardine »
devient un libellé de plus de cette activité : la question est comprise même sans la reformulation de l'agent.

1. Collecter : dans les tours journalisés (anonymisés), les appels à conseiller : le message du visiteur et l'activité
   que la reformulation de l'agent a trouvée (proximité d'au moins PROXIMITE_MIN).
2. Proposer : un mot du visiteur (pas un nombre ; l'arabizi garde ses chiffres-lettres) vu dans SESSIONS_MIN conversations distinctes,
   avec la même activité dans au moins PART_MIN des cas, et qui seul n'y mène pas aujourd'hui.
3. Vérifier : mot anonyme et sans chiffre ; activité existante ; pas déjà le libellé d'une autre activité ; une fois
   actif, il mène à cette activité ; tests des outils réussis.
4. Publier (agent_appris_synonymes, relu en direct ; ajouté au graphe, graphe nommé appris/<id>, à la prochaine
   construction, sous SHACL et OWL RL) ou rejeter ; tout au journal. Annuler : désactivé, journal gardé.
"""
import argparse, json, re, subprocess, sys
from collections import defaultdict
from dalila.config import RACINE
from dalila.apprentissage.lieux_appris import _ecrire, _lire_rw, _decider
from dalila.harnais.garde_fous import anonymiser

SESSIONS_MIN, PART_MIN = 2, 0.8
PROXIMITE_MIN = 0.55     # l'activité trouvée par la reformulation de l'agent doit être nette
DEJA_COMPRIS = 0.5       # le mot seul mène déjà à l'activité avec cette proximité : rien à apprendre


def _activite(texte):
    from dalila.traitement.graphe import _activites
    n, lib, _, sim = _activites(texte, k=1)[0]
    return n, lib, sim


def mot_admis(m):
    """Un mot, pas un chiffre (BNF18) : au moins 3 lettres, au plus 2 chiffres ; l'arabizi en a (« 7out », « ma3mel »)."""
    lettres, chiffres = sum(c.isalpha() for c in m), sum(c.isdigit() for c in m)
    return lettres >= 3 and chiffres <= 2 and 4 <= len(m) <= 40


def _mots(texte):
    return {m for m in re.findall(r"\w+", (texte or "").lower()) if mot_admis(m)}


def collecter():
    tours = _lire_rw("SELECT session_id, texte_anonymise, outils FROM agent_turns WHERE session_id IS NOT NULL "
                     "AND outils LIKE '%%conseiller%%'")
    preuves = defaultdict(lambda: defaultdict(set))   # mot -> (noeud, libellé) -> sessions
    for t in tours:
        for o in json.loads(t["outils"] or "[]"):
            secteur = (o.get("arguments") or {}).get("secteur") if o.get("outil") == "conseiller" else None
            if not secteur:
                continue
            n, lib, sim = _activite(secteur)
            if sim < PROXIMITE_MIN:
                continue
            for m in _mots(t["texte_anonymise"]) - _mots(secteur):   # les mots du visiteur, pas ceux de l'agent
                preuves[m][(n, lib)].add(t["session_id"])
    return preuves


def proposer(preuves):
    deja = {(json.loads(c["payload"])["terme"], json.loads(c["payload"])["concept_uri"])
            for c in _lire_rw("SELECT payload FROM agent_learning_candidates WHERE kind = 'synonyme'")}
    nouveaux = []
    for mot, cibles in preuves.items():
        (n, lib), sessions = max(cibles.items(), key=lambda x: len(x[1]))
        total = sum(len(s) for s in cibles.values())
        if len(sessions) < SESSIONS_MIN or len(sessions) / total < PART_MIN or (mot, n) in deja:
            continue
        n_seul, _, sim_seul = _activite(mot)
        if n_seul == n and sim_seul >= DEJA_COMPRIS:
            continue  # déjà compris sans aide
        payload = {"terme": mot, "concept_uri": n, "concept_libelle": lib}
        cid = _ecrire("INSERT INTO agent_learning_candidates (kind, payload, sessions_preuve, status) VALUES "
                      "('synonyme', %s, %s, 'propose')", json.dumps(payload, ensure_ascii=False), json.dumps(sorted(sessions)))
        nouveaux.append((cid, payload))
    return nouveaux


def verifier_et_publier(cid, payload, tests=True):
    from dalila.traitement.graphe import _index_activites
    terme, n = payload["terme"], payload["concept_uri"]
    noeuds, libelles, _, _ = _index_activites()
    controles = {"anonyme_et_pas_un_nombre": anonymiser(terme) == terme and mot_admis(terme),
                 "concept_existe": n in noeuds,
                 "pas_libelle_d_un_autre": all(l.lower() != terme.lower() for x, l in zip(noeuds, libelles) if x != n)}
    if not all(controles.values()):
        return _decider(cid, None, controles, "rejete")
    _ecrire("INSERT INTO agent_appris_synonymes (terme, concept_uri, concept_libelle, candidat_id, actif) VALUES "
            "(%s, %s, %s, %s, 1) ON DUPLICATE KEY UPDATE actif = 1, candidat_id = VALUES(candidat_id)",
            terme, n, payload.get("concept_libelle"), cid)
    sid = _lire_rw("SELECT id FROM agent_appris_synonymes WHERE terme = %s AND concept_uri = %s", terme, n)[0]["id"]
    controles["mene_a_l_activite"] = _activite(terme)[0] == n
    if tests and controles["mene_a_l_activite"]:
        p = subprocess.run([sys.executable, "-m", "tests.traitement.test_outils"], cwd=RACINE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        controles["tests_des_outils"] = p.returncode == 0
    ok = all(controles.values())
    if not ok:
        _ecrire("UPDATE agent_appris_synonymes SET actif = 0 WHERE id = %s", sid)
    decision, controles = _decider(cid, None, controles, "publie" if ok else "rejete")
    if ok:  # le journal désigne le graphe nommé de l'ajout
        _ecrire("UPDATE agent_learning_journal SET graphe_nomme = %s WHERE candidate_id = %s", f"appris/{sid}", cid)
    return decision, controles


def annuler(sid, par="administrateur"):
    r = _lire_rw("SELECT candidat_id FROM agent_appris_synonymes WHERE id = %s", sid)
    if not r:
        return False
    _ecrire("UPDATE agent_appris_synonymes SET actif = 0 WHERE id = %s", sid)
    _ecrire("UPDATE agent_learning_journal SET revoked_at = CURRENT_TIMESTAMP, revoked_by = %s "
            "WHERE graphe_nomme = %s AND revoked_at IS NULL", par, f"appris/{sid}")
    _ecrire("UPDATE agent_learning_candidates SET status = 'annule' WHERE id = %s", r[0]["candidat_id"])
    return True


def cycle(tests=True):
    return [(p, *verifier_et_publier(cid, p, tests)) for cid, p in proposer(collecter())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lister", action="store_true")
    ap.add_argument("--annuler", type=int)
    ap.add_argument("--sans-tests", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.annuler:
        print("annulé" if annuler(a.annuler) else "introuvable")
    elif a.lister:
        for r in _lire_rw("SELECT s.id, s.terme, s.concept_libelle, s.actif, j.created_at, j.revoked_at FROM "
                          "agent_appris_synonymes s LEFT JOIN agent_learning_journal j ON j.candidate_id = s.candidat_id"):
            print(f"n° {r['id']} « {r['terme']} » -> {r['concept_libelle']} | actif={r['actif']} | publié {r['created_at']} "
                  f"| annulé {r['revoked_at']}")
    else:
        for p, decision, controles in cycle(tests=not a.sans_tests):
            print(f"« {p['terme']} » -> {p['concept_libelle']} : {decision} {controles}")


if __name__ == "__main__":
    main()
