"""Routes d'administration de Dalila, pour l'agent de l'AFI (BF12, BF15, BF21). Lecture seule, sauf « Annuler ».

GET  /admin/api/besoins                   questions mal traitées (repli ou « pas utile »), les plus fréquentes d'abord
                                          ?depuis=AAAA-MM-JJ  ?tout=1 (aussi les questions sans problème)
GET  /admin/api/apprentissage             journal de l'apprentissage : noms de lieux et synonymes, avec leurs contrôles
POST /admin/api/apprentissage/{genre}/{id}/annuler   genre : « lieu » ou « synonyme » ; le journal garde la trace
GET  /admin/api/sources                   état de chaque URL de la configuration (lue, en erreur, à relire, en retard)

Accès : avec DALILA_ADMIN_CLE dans .env, l'en-tête X-Cle-Admin doit la porter ; sans clé, seulement depuis la machine
elle-même (127.0.0.1). Les questions affichées sont celles du journal, déjà anonymisées (BNF16).
"""
import datetime as dt, hmac, json, os
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

LOCAL = {"127.0.0.1", "::1", "localhost", "testclient"}


def autoriser(request: Request, x_cle_admin: str | None = Header(None)):
    cle = os.environ.get("DALILA_ADMIN_CLE", "").strip()
    if cle:
        if not x_cle_admin or not hmac.compare_digest(x_cle_admin.encode(), cle.encode()):
            raise HTTPException(401, "clé d'administration absente ou fausse")
    elif (request.client.host if request.client else "") not in LOCAL:
        raise HTTPException(403, "administration ouverte seulement depuis le serveur (ou avec DALILA_ADMIN_CLE)")


routeur = APIRouter(prefix="/admin/api", tags=["administration"], dependencies=[Depends(autoriser)])


def _texte(v):
    return v.isoformat(sep=" ", timespec="seconds") if isinstance(v, (dt.datetime, dt.date)) else v


def _json(v):
    if not v:
        return None
    try:
        return json.loads(v) if isinstance(v, (str, bytes)) else v
    except ValueError:
        return None


def _base_indisponible(ex):
    return HTTPException(503, f"base de données injoignable ({type(ex).__name__})")


# ---------------------------------------------------------------- BF12 : questions mal traitées
@routeur.get("/besoins")
def questions_mal_traitees(depuis: dt.date | None = None, tout: bool = False):
    from dalila.apprentissage.besoins import besoins
    try:
        lignes = besoins(depuis.isoformat() if depuis else None, tout)
    except Exception as ex:  # noqa: BLE001
        raise _base_indisponible(ex)
    return [{"question": l["question"], "langues": l["langues"].split(","), "posee": l["posee"], "repli": l["repli"],
             "pas_utile": l["pas_utile"], "utile": l["utile"], "commentaires": l["commentaires"],
             "derniere_fois": _texte(l["derniere_fois"])} for l in lignes]


# ---------------------------------------------------------------- BF21 : journal de l'apprentissage
SQL_JOURNAL = """
SELECT c.id candidat, c.kind, c.payload, c.sessions_preuve, c.status, c.created_at propose_le,
       j.checks, j.decision, j.created_at decide_le, j.revoked_at, j.revoked_by,
       l.id lieu_id, l.actif lieu_actif, s.id synonyme_id, s.actif synonyme_actif
FROM agent_learning_candidates c
LEFT JOIN agent_learning_journal j ON j.candidate_id = c.id
LEFT JOIN agent_appris_lieux l ON l.candidat_id = c.id AND c.kind = 'alias_lieu'
LEFT JOIN agent_appris_synonymes s ON s.candidat_id = c.id AND c.kind = 'synonyme'
WHERE c.kind IN ('alias_lieu', 'synonyme')
ORDER BY COALESCE(j.created_at, c.created_at) DESC, c.id DESC
"""


def ligne_journal(r):
    p = _json(r["payload"]) or {}
    lieu = r["kind"] == "alias_lieu"
    appris = r["lieu_id"] if lieu else r["synonyme_id"]
    actif = r["lieu_actif"] if lieu else r["synonyme_actif"]
    return {
        "candidat": r["candidat"],
        "genre": "lieu" if lieu else "synonyme",
        "terme": p.get("alias") if lieu else p.get("terme"),
        "cible": (f"{p.get('cible_nom')} ({p.get('type')})" if lieu else p.get("concept_libelle")) or "",
        "conversations": len(_json(r["sessions_preuve"]) or []),
        "statut": r["status"],                    # propose, publie, rejete, annule
        "controles": _json(r["checks"]) or {},
        "propose_le": _texte(r["propose_le"]),
        "decide_le": _texte(r["decide_le"]),
        "annule_le": _texte(r["revoked_at"]),
        "annule_par": r["revoked_by"],
        "appris_id": appris,
        "actif": bool(actif),
        "annulable": bool(appris) and bool(actif) and r["status"] == "publie",
    }


@routeur.get("/apprentissage")
def journal_apprentissage():
    from dalila.apprentissage.lieux_appris import _lire_rw
    try:
        lignes = _lire_rw(SQL_JOURNAL)
    except Exception as ex:  # noqa: BLE001
        raise _base_indisponible(ex)
    vus, sortie = set(), []
    for r in lignes:   # une ligne par candidat (la décision la plus récente)
        if r["candidat"] not in vus:
            vus.add(r["candidat"])
            sortie.append(ligne_journal(r))
    return sortie


class Annulation(BaseModel):
    par: str = Field("administrateur", max_length=80)


@routeur.post("/apprentissage/{genre}/{appris_id}/annuler")
def annuler(genre: str, appris_id: int, a: Annulation | None = None):
    if genre == "lieu":
        from dalila.apprentissage.lieux_appris import annuler as faire
    elif genre == "synonyme":
        from dalila.apprentissage.synonymes_appris import annuler as faire
    else:
        raise HTTPException(404, "genre inconnu : « lieu » ou « synonyme »")
    try:
        ok = faire(appris_id, par=(a.par.strip() if a and a.par.strip() else "administrateur"))
    except Exception as ex:  # noqa: BLE001
        raise _base_indisponible(ex)
    if not ok:
        raise HTTPException(404, "élément appris introuvable")
    return {"ok": True}


# ---------------------------------------------------------------- BF15 : état des URL
def etat_source(conf, e, maintenant):
    """État d'une URL de la configuration : inactive, jamais_lue, erreur, a_relire, en_retard ou ok."""
    if conf.get("actif", "1").strip() != "1":
        return "inactive"
    if not e or not e.get("derniere_tentative"):
        return "jamais_lue"
    if e.get("echecs_consecutifs", 0) > 0:
        return "erreur"
    if e.get("a_relire"):
        return "a_relire"
    ok = e.get("derniere_lecture_ok")
    delai = float(conf.get("delai_jours") or 7)
    if not ok or maintenant - dt.datetime.fromisoformat(str(ok)) > dt.timedelta(days=2 * delai):
        return "en_retard"
    return "ok"


def _etat_depuis_la_base():
    """Copie de l'état dans agent_source_status, quand le fichier d'état n'est pas sur cette machine."""
    from dalila.apprentissage.lieux_appris import _lire_rw
    etat = {}
    for r in _lire_rw("SELECT url, last_ok_at, last_error, last_error_at FROM agent_source_status"):
        etat[r["url"]] = {"derniere_lecture_ok": _texte(r["last_ok_at"]),
                          "derniere_tentative": _texte(r["last_error_at"] or r["last_ok_at"]),
                          "echecs_consecutifs": 1 if r["last_error"] else 0, "derniere_erreur": r["last_error"],
                          "derniere_erreur_le": _texte(r["last_error_at"])}
    return etat


@routeur.get("/sources")
def etat_des_sources():
    from dalila.sources.inventaire import lire_config
    from dalila.sources.rafraichir import Etat
    config = lire_config()
    etat = Etat().sources
    origine = "fichier"
    if not etat:
        try:
            etat, origine = _etat_depuis_la_base(), "base"
        except Exception:  # noqa: BLE001
            origine = "aucune"
    maintenant = dt.datetime.now()
    sources = []
    for c in config:
        e = etat.get(c["url"], {})
        sources.append({
            "url": c["url"], "organisme": c.get("organisme") or e.get("organisme"), "type": c.get("type"),
            "delai_jours": c.get("delai_jours"), "utilise_par": c.get("utilise_par"),
            "etat": etat_source(c, e, maintenant),
            "derniere_lecture_ok": e.get("derniere_lecture_ok"), "derniere_tentative": e.get("derniere_tentative"),
            "erreur": e.get("derniere_erreur") if e.get("echecs_consecutifs", 0) > 0 else None,
            "echecs": e.get("echecs_consecutifs", 0), "statut_http": e.get("statut_http"),
        })
    resume = {}
    for s in sources:
        resume[s["etat"]] = resume.get(s["etat"], 0) + 1
    return {"origine": origine, "total": len(sources), "resume": resume, "sources": sources}
