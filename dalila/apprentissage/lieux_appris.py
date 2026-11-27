"""Apprentissage contrôlé des noms de lieux (BF18, BF19, BF21, BNF15 à BNF18).

    .venv\\Scripts\\python -m dalila.apprentissage.lieux_appris              cycle : collecter -> proposer -> vérifier -> publier
    .venv\\Scripts\\python -m dalila.apprentissage.lieux_appris --lister     candidats et noms appris, avec leur état
    .venv\\Scripts\\python -m dalila.apprentissage.lieux_appris --annuler 7  retire le nom appris n° 7 (journal gardé)

Ce qui s'apprend : « ce nom désigne ce lieu » (« Qassrin » -> gouvernorat de Kasserine), seulement. Jamais un prix, une
disponibilité, une surface ou une condition venus d'un visiteur (BNF18) : un nom qui contient des chiffres est refusé.

1. Collecter : dans les tours journalisés (agent_turns, déjà anonymisés), les noms de lieu que l'agent n'a pas trouvés,
   avec le lieu finalement retenu : dans le même tour (trouvé dans le message du visiteur) ou au tour suivant de la même
   conversation (le visiteur s'est corrigé).
2. Proposer : un nom vu dans au moins SESSIONS_MIN conversations distinctes, toujours pour le même lieu
   (agent_learning_candidates, avec les conversations qui le prouvent).
3. Vérifier (BF19) : nom anonyme et sans chiffre ; lieu existant ; nom pas déjà pris par un autre lieu ; une fois actif,
   il désigne ce lieu et rien d'autre ; tous les noms officiels se résolvent comme avant ; tests des outils réussis.
4. Publier ou rejeter : table agent_appris_lieux (actif ou non) ; chaque décision dans agent_learning_journal, avec ses
   contrôles. Annuler : le nom est désactivé, le journal garde la trace (date, auteur).
"""
import argparse, json, re, subprocess, sys
from collections import defaultdict
from dalila.config import RACINE, db
from dalila.harnais.garde_fous import masquer
from dalila.traitement.base import q
from dalila.traitement.lieux import EntreeLieu, _norm, resoudre_lieu

SESSIONS_MIN = 2     # BNF18 : jamais appris d'une seule conversation
PART_MIN = 0.8       # part des preuves qui désignent le même lieu
OUTILS_LIEU = {"chercher_lots": "lieu", "lister_zones": "lieu", "fiche_zone": "zone_id"}


def _ecrire(sql, *p):
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.lastrowid or cur.rowcount
    finally:
        con.close()


def _lire_rw(sql, *p):
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            return cur.fetchall()
    finally:
        con.close()


def _lieu(texte):
    """(type, id, nom) du lieu désigné sans ambiguïté par ce texte, sinon None."""
    if not texte:
        return None
    r = resoudre_lieu(EntreeLieu(texte=str(texte)[:100]))
    if not r.lieux or r.ambigu:
        return None
    l0 = r.lieux[0]
    return (l0.type, str(l0.id), l0.nom)


# ---------------------------------------------------------------- 1. collecter
def collecter():
    """-> {(nom normalisé, type, id, nom du lieu): {"alias": nom tel qu'écrit, "sessions": {...}}}"""
    tours = _lire_rw("SELECT id, session_id, outils FROM agent_turns WHERE session_id IS NOT NULL ORDER BY session_id, id")
    par_session = defaultdict(list)
    for t in tours:
        par_session[t["session_id"]].append(t)
    preuves = {}
    for session, ts in par_session.items():
        appels = []  # (n° du tour, nom demandé par le modèle, lieu retenu ou None)
        for i, t in enumerate(ts):
            for o in json.loads(t["outils"] or "[]"):
                champ = OUTILS_LIEU.get(o.get("outil"))
                if not champ:
                    continue
                demande = (o.get("arguments_modele") or o.get("arguments") or {}).get(champ)
                final = (o.get("arguments") or {}).get(champ)
                if demande:
                    appels.append((i, demande, _lieu(final) if final else None))
        for k, (i, demande, retenu) in enumerate(appels):
            if _lieu(demande):
                continue  # nom déjà compris : rien à apprendre
            cible = retenu or next((r for j, d, r in appels[k + 1:] if j > i and r), None)  # même tour, sinon correction
            if not cible:
                continue
            cle = (_norm(demande), *cible)
            e = preuves.setdefault(cle, {"alias": str(demande).strip(), "sessions": set()})
            e["sessions"].add(session)
    return preuves


# ---------------------------------------------------------------- 2. proposer
def proposer(preuves):
    par_nom = defaultdict(dict)
    for (n, typ, ident, nom), e in preuves.items():
        par_nom[n][(typ, ident, nom)] = e
    deja = {(c["payload"]) for c in _lire_rw("SELECT payload FROM agent_learning_candidates WHERE kind = 'alias_lieu'")}
    deja = {(json.loads(p)["alias_norm"], json.loads(p)["type"], json.loads(p)["cible_id"]) for p in deja}
    nouveaux = []
    for n, cibles in par_nom.items():
        total = sum(len(e["sessions"]) for e in cibles.values())
        (typ, ident, nom), e = max(cibles.items(), key=lambda x: len(x[1]["sessions"]))
        if len(e["sessions"]) < SESSIONS_MIN or len(e["sessions"]) / total < PART_MIN or (n, typ, ident) in deja:
            continue
        payload = {"alias": e["alias"], "alias_norm": n, "type": typ, "cible_id": ident, "cible_nom": nom}
        cid = _ecrire("INSERT INTO agent_learning_candidates (kind, payload, sessions_preuve, status) VALUES "
                      "('alias_lieu', %s, %s, 'propose')", json.dumps(payload, ensure_ascii=False),
                      json.dumps(sorted(e["sessions"])))
        nouveaux.append((cid, payload))
    return nouveaux


# ---------------------------------------------------------------- 3. vérifier
def _noms_officiels():
    zones = q("SELECT nom_fr, nom_ar FROM v_pub_zones")
    gouv = q("SELECT nom_fr, nom_ar FROM dalila_gouvernorats")
    alias = q("SELECT alias FROM dalila_zone_alias")
    return sorted({n for r in zones + gouv for n in (r["nom_fr"], r["nom_ar"]) if n} | {a["alias"] for a in alias})


def _resolutions(noms):
    return {n: [(l.type, str(l.id)) for l in resoudre_lieu(EntreeLieu(texte=n[:100])).lieux][:2] for n in noms}


def verifier_et_publier(cid, payload, tests=True):
    alias, typ, ident = payload["alias"], payload["type"], payload["cible_id"]
    controles = {}
    controles["anonyme_sans_chiffre"] = masquer(alias) == alias and not re.search(r"\d", alias) and 2 <= len(alias) <= 60
    existe = q("SELECT 1 FROM v_pub_zones WHERE zone_id = %s", ident) if typ == "zone" else \
        q("SELECT 1 FROM dalila_gouvernorats WHERE code = %s", ident)
    controles["lieu_existe"] = bool(existe)
    avant = _lieu(alias)
    controles["nom_libre"] = avant is None  # ni compris déjà, ni pris par un autre lieu
    if not all(controles.values()):
        return _decider(cid, None, controles, "rejete")
    noms = _noms_officiels()
    ref = _resolutions(noms)
    lid = _ecrire("INSERT INTO agent_appris_lieux (alias, type, cible_id, candidat_id, actif) VALUES (%s, %s, %s, %s, 1) "
                  "ON DUPLICATE KEY UPDATE actif = 1, candidat_id = VALUES(candidat_id)", alias, typ, ident, cid)
    lid = _lire_rw("SELECT id FROM agent_appris_lieux WHERE alias = %s AND type = %s AND cible_id = %s", alias, typ, ident)[0]["id"]
    apres = _lieu(alias)
    controles["designe_ce_lieu"] = bool(apres) and apres[:2] == (typ, ident)
    changes = [n for n, r in _resolutions(noms).items() if r != ref[n]]
    controles["noms_officiels_inchanges"] = not changes
    if changes:
        controles["noms_changes"] = changes[:5]
    if tests and controles["designe_ce_lieu"] and not changes:
        p = subprocess.run([sys.executable, "-m", "tests.traitement.test_outils"], cwd=RACINE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        controles["tests_des_outils"] = p.returncode == 0
    ok = all(v for k, v in controles.items() if k != "noms_changes")
    if not ok:
        _ecrire("UPDATE agent_appris_lieux SET actif = 0 WHERE id = %s", lid)
    return _decider(cid, lid if ok else None, controles, "publie" if ok else "rejete")


def _decider(cid, lid, controles, decision):
    _ecrire("UPDATE agent_learning_candidates SET status = %s WHERE id = %s", decision, cid)
    _ecrire("INSERT INTO agent_learning_journal (candidate_id, checks, decision, graphe_nomme) VALUES (%s, %s, %s, %s)",
            cid, json.dumps(controles, ensure_ascii=False), decision, f"agent_appris_lieux/{lid}" if lid else None)
    return decision, controles


# ---------------------------------------------------------------- annuler, lister
def annuler(lid, par="administrateur"):
    r = _lire_rw("SELECT candidat_id FROM agent_appris_lieux WHERE id = %s", lid)
    if not r:
        return False
    _ecrire("UPDATE agent_appris_lieux SET actif = 0 WHERE id = %s", lid)
    _ecrire("UPDATE agent_learning_journal SET revoked_at = CURRENT_TIMESTAMP, revoked_by = %s "
            "WHERE graphe_nomme = %s AND revoked_at IS NULL", par, f"agent_appris_lieux/{lid}")
    _ecrire("UPDATE agent_learning_candidates SET status = 'annule' WHERE id = %s", r[0]["candidat_id"])
    return True


def lister():
    return _lire_rw("SELECT c.id candidat, c.status, c.payload, a.id appris, a.actif, j.checks, j.created_at, j.revoked_at "
                    "FROM agent_learning_candidates c LEFT JOIN agent_appris_lieux a ON a.candidat_id = c.id "
                    "LEFT JOIN agent_learning_journal j ON j.candidate_id = c.id WHERE c.kind = 'alias_lieu' ORDER BY c.id")


def cycle(tests=True):
    nouveaux = proposer(collecter())
    return [(p, *verifier_et_publier(cid, p, tests)) for cid, p in nouveaux]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lister", action="store_true")
    ap.add_argument("--annuler", type=int)
    ap.add_argument("--sans-tests", action="store_true", help="sans les tests des outils (plus rapide ; essais seulement)")
    a = ap.parse_args()
    if a.annuler:
        print("annulé" if annuler(a.annuler) else "introuvable")
    elif a.lister:
        for r in lister():
            p = json.loads(r["payload"])
            print(f"candidat {r['candidat']} [{r['status']}] « {p['alias']} » -> {p['type']} {p['cible_nom']} | appris n° "
                  f"{r['appris']} actif={r['actif']} | annulé le {r['revoked_at']}")
    else:
        for p, decision, controles in cycle(tests=not a.sans_tests):
            print(f"« {p['alias']} » -> {p['type']} {p['cible_nom']} : {decision} {controles}")


if __name__ == "__main__":
    main()
