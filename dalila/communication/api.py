"""API HTTP de Dalila, au contrat de la carte de l'AFI (BNF11).

    .venv\\Scripts\\python -m uvicorn dalila.communication.api:app --host 0.0.0.0 --port 8000

POST /carte/chatbot        {message, history, lang, contexte, session_id}
                           -> {message, log_id, source, action, duree_s}
POST /carte/chatbot/avis   {log_id, utile}  -> {ok}
GET  /sante                -> état du service (modèle prêt, base joignable)

Le message rendu porte les balises [[ZONE:id:nom]], [[LOT:id:nom]], [[CHOIX:texte]], [[PDF:url:libellé]] que la carte
rend cliquables. source : "dalila" (réponse vérifiée) ou "repli" (réponse de secours, contact de l'AFI). action :
"choix" si le visiteur doit choisir parmi des boutons [[CHOIX]], sinon null.

Jamais d'erreur brute (BNF4) : moteur arrêté, base injoignable ou délai dépassé donnent une réponse en texte. Chaque tour
est journalisé anonymisé (agent_turns, compte dalila_rw) ; une question sans réponse fiable est gardée pour l'AFI
(agent_needs, BF12, BF24). Un seul calcul à la fois : sur processeur, deux réponses en parallèle seraient toutes deux
hors délai.
"""
import json, logging, os, threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dalila.config import db
from dalila.harnais.agent import Agent
from dalila.harnais.consignes import REPLI
from dalila.harnais.garde_fous import masquer

log = logging.getLogger("dalila.api")
AGENT = Agent()
_CALCUL = threading.Lock()
_ETAT = {"pret": False}


@asynccontextmanager
async def _demarrage(app):
    if os.environ.get("DALILA_PRECHAUFFER", "1") == "1":  # 40 à 60 s une fois, au lieu de la première question
        threading.Thread(target=_prechauffer, daemon=True).start()
    else:
        _ETAT["pret"] = True
    yield


def _prechauffer():
    try:
        with _CALCUL:
            AGENT.prechauffer()
    except Exception:  # noqa: BLE001
        log.exception("préchauffage")
    _ETAT["pret"] = True


app = FastAPI(title="Dalila", version="1.0", lifespan=_demarrage)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("DALILA_CORS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])


class Message(BaseModel):
    role: str
    content: str = ""


class Question(BaseModel):
    message: str = Field("", max_length=2000, description="tronqué à 500 caractères par le harnais")
    history: list[Message] = Field(default_factory=list, max_length=100, description="20 derniers messages gardés")
    lang: str | None = Field(None, max_length=10, description="langue de l'interface (fr, ar, en, de, tr...)")
    contexte: dict | None = Field(None, description="page, zone, lot ou favoris sélectionnés sur la carte")
    session_id: str | None = Field(None, max_length=64)


class Reponse(BaseModel):
    message: str
    log_id: int | None
    source: str
    action: str | None
    duree_s: float


class Avis(BaseModel):
    log_id: int
    utile: bool


def _ecrire(sql, *p):
    """Journal : une panne de la base ne doit jamais empêcher la réponse."""
    try:
        con = db("rw")
        try:
            with con.cursor() as cur:
                cur.execute(sql, p)
                return cur.lastrowid or cur.rowcount  # identifiant créé, ou nombre de lignes modifiées
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        log.exception("journal")
        return None


@app.post("/carte/chatbot", response_model=Reponse)
def chatbot(q: Question):
    lang = (q.lang or "fr").strip().lower()[:10]
    try:
        with _CALCUL:
            r = AGENT.repondre(q.message, historique=[m.model_dump() for m in q.history], lang=lang,
                               contexte=q.contexte)
    except Exception as ex:  # noqa: BLE001  (BNF4)
        log.exception("agent")
        r = {"reponse": REPLI.get(lang[:2], REPLI["fr"]), "source": "repli", "outils": [], "duree_s": 0.0,
             "erreur": type(ex).__name__}
    texte = masquer((q.message or "").strip()[:500])
    outils = [{"outil": o["outil"], "arguments": o.get("arguments")} for o in r["outils"]]
    log_id = _ecrire("INSERT INTO agent_turns (session_id, texte_anonymise, langue, outils, garde_faits, latence_ms, "
                     "source) VALUES (%s, %s, %s, %s, %s, %s, %s)", q.session_id, texte, lang,
                     json.dumps(outils, ensure_ascii=False), "ancre" if r["source"] == "dalila" else "repli",
                     int(r["duree_s"] * 1000), r["source"])
    if r["source"] == "repli" and texte:
        _ecrire("INSERT INTO agent_needs (texte_anonymise, langue, raison) VALUES (%s, %s, %s)",
                texte, lang, (r.get("erreur") or "repli")[:60])
    return Reponse(message=r["reponse"], log_id=log_id, source=r["source"],
                   action="choix" if "[[CHOIX:" in r["reponse"] else None, duree_s=r["duree_s"])


@app.post("/carte/chatbot/avis")
def avis(a: Avis):
    ok = bool(_ecrire("UPDATE agent_turns SET avis = %s WHERE id = %s", 1 if a.utile else 0, a.log_id))
    return {"ok": ok}


@app.get("/sante")
def sante():
    try:
        from dalila.traitement.base import q as lire
        base = bool(lire("SELECT 1 n"))
    except Exception:  # noqa: BLE001
        base = False
    return {"pret": _ETAT["pret"], "base": base, "modele": AGENT.modele}
