"""API HTTP de Dalila, au contrat de la carte de l'AFI (BNF11).

    .venv\\Scripts\\python -m uvicorn dalila.communication.api:app --host 0.0.0.0 --port 8000

POST /carte/chatbot        {message, history, lang, contexte, session_id}
                           -> {message, log_id, source, action, duree_s}
POST /carte/chatbot/avis   {log_id, utile, commentaire facultatif}  -> {ok}
POST /carte/voix/transcrire  fichier « audio » (webm, ogg, wav...) + lang facultatif -> {texte, langue, confiance, duree_s}
POST /carte/voix/lire       {texte, lang} -> audio/wav ; dialecte lu par la voix arabe : en-tête X-Dalila-Lecture (BF8)
POST /carte/etude           {session_id, lang} -> première question de l'étude de projet guidée (10 questions, PDF)
GET  /carte/etude/{id}.pdf  -> l'étude en PDF ; pendant une étude, /carte/chatbot reçoit les réponses aux questions
GET  /sante                -> état du service (modèle prêt, base joignable)

Voix (dalila/voix) : l'audio du visiteur est décodé en mémoire, jamais écrit ni gardé (BNF8) ; le texte reconnu est
rendu à l'interface, qui l'affiche avant de l'envoyer à /carte/chatbot. Le consentement au micro est demandé par
l'interface avant le premier enregistrement.

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
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
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
_VOIX = threading.Lock()  # la voix ne passe pas derrière une réponse écrite (BNF3 : 4 s) ; un enregistrement à la fois


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
                   allow_methods=["GET", "POST"], allow_headers=["*"], expose_headers=["X-Dalila-Lecture"])


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
    langue: str | None = Field(None, description="langue détectée du message : fr, en, ar, de, tr, tn (tunisien), "
                                                 "dz (algérien), ly (libyen)")
    session_id: str | None = Field(None, description="session (créée si absente : à renvoyer pour suivre une étude)")
    ecriture: str | None = Field(None, description="arabe ou latin")


class Avis(BaseModel):
    log_id: int
    utile: bool
    commentaire: str | None = Field(None, max_length=500, description="facultatif (flux F06), anonymisé")


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
    from dalila.traitement import etude
    session = q.session_id or __import__("secrets").token_hex(8)
    if q.session_id and etude.en_cours(q.session_id):  # étude guidée en cours : la réponse va à l'entretien, sans modèle
        return _reponse_etude(etude.repondre(q.session_id, q.message), session, q, lang)
    try:
        with _CALCUL:
            r = AGENT.repondre(q.message, historique=[m.model_dump() for m in q.history], lang=lang,
                               contexte=q.contexte)
    except Exception as ex:  # noqa: BLE001  (BNF4)
        log.exception("agent")
        r = {"reponse": REPLI.get(lang[:2], REPLI["fr"]), "source": "repli", "outils": [], "duree_s": 0.0,
             "erreur": type(ex).__name__}
    det = r.get("langue_detectee") or {}
    if r["source"] == "etude_demandee":  # le modèle a reconnu une demande d'étude : l'entretien commence
        return _reponse_etude(etude.commencer(session, det.get("langue") or lang, q.message), session, q, lang, det)
    texte = masquer((q.message or "").strip()[:500])
    langue = det.get("langue") or lang
    outils = [{"outil": o["outil"], "arguments": o.get("arguments"), **({"arguments_modele": o["arguments_modele"]}
              if o.get("arguments_modele") else {})} for o in r["outils"]]  # lieu inconnu : pour l'apprentissage
    log_id = _ecrire("INSERT INTO agent_turns (session_id, texte_anonymise, langue, outils, garde_faits, latence_ms, "
                     "source, reponse, script) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", q.session_id, texte, langue,
                     json.dumps(outils, ensure_ascii=False), "ancre" if r["source"] == "dalila" else "repli",
                     int(r["duree_s"] * 1000), r["source"], masquer(r.get("texte_modele") or "")[:4000] or None,
                     det.get("ecriture"))
    if r["source"] == "repli" and texte:
        _ecrire("INSERT INTO agent_needs (texte_anonymise, langue, raison) VALUES (%s, %s, %s)",
                texte, langue, (r.get("erreur") or "repli")[:60])
    return Reponse(message=r["reponse"], log_id=log_id, source=r["source"],
                   action="choix" if "[[CHOIX:" in r["reponse"] else None, duree_s=r["duree_s"],
                   langue=det.get("langue"), ecriture=det.get("ecriture"), session_id=session)


def _reponse_etude(e, session, q, lang, det=None):
    det = det or {}
    log_id = _ecrire("INSERT INTO agent_turns (session_id, texte_anonymise, langue, outils, garde_faits, latence_ms, "
                     "source) VALUES (%s, %s, %s, %s, %s, %s, %s)", session, masquer((q.message or "")[:500]),
                     det.get("langue") or lang, json.dumps([{"outil": "etude_de_projet"}]), "etude", 0, "etude")
    return Reponse(message=e["message"], log_id=log_id, source="etude",
                   action="choix" if "[[CHOIX:" in e["message"] else ("etude_pdf" if e.get("pdf") else None),
                   duree_s=0.0, langue=det.get("langue"), ecriture=det.get("ecriture"), session_id=session)


class DebutEtude(BaseModel):
    session_id: str = Field(..., max_length=64)
    lang: str | None = Field(None, max_length=10)


@app.post("/carte/etude", response_model=Reponse)
def etude_commencer(d: DebutEtude):
    from dalila.traitement import etude
    q = Question(message="", lang=d.lang, session_id=d.session_id)
    return _reponse_etude(etude.commencer(d.session_id, d.lang or "fr"), d.session_id, q, d.lang or "fr")


@app.get("/carte/etude/{jeton}.pdf")
def etude_pdf(jeton: str):
    from fastapi.responses import FileResponse
    from dalila.traitement import etude
    p = etude.chemin_pdf(jeton)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="application/pdf", filename="etude-de-projet-dalila.pdf")


@app.post("/carte/chatbot/avis")
def avis(a: Avis):
    ok = bool(_ecrire("UPDATE agent_turns SET avis = %s, avis_commentaire = %s WHERE id = %s", 1 if a.utile else 0,
                      masquer(a.commentaire.strip())[:500] if a.commentaire and a.commentaire.strip() else None, a.log_id))
    return {"ok": ok}


@app.get("/sante")
def sante():
    try:
        from dalila.traitement.base import q as lire
        base = bool(lire("SELECT 1 n"))
    except Exception:  # noqa: BLE001
        base = False
    return {"pret": _ETAT["pret"], "base": base, "modele": AGENT.modele}


class Lecture(BaseModel):
    texte: str = Field(..., max_length=4000)
    lang: str | None = Field(None, max_length=10)


@app.post("/carte/voix/transcrire")
async def voix_transcrire(audio: UploadFile = File(...), lang: str | None = Form(None)):
    from dalila.voix.reconnaissance import TAILLE_MAX, AudioInvalide, transcrire
    octets = await audio.read(TAILLE_MAX + 1)  # en mémoire seulement : rien n'est écrit sur disque (BNF8)
    try:
        with _VOIX:
            return transcrire(octets, lang)
    except AudioInvalide as ex:
        raise HTTPException(422, str(ex)) from ex
    finally:
        del octets


@app.post("/carte/voix/lire")
def voix_lire(l: Lecture):
    from dalila.voix.synthese import lire_avec_note
    try:
        with _VOIX:
            wav, note = lire_avec_note(l.texte, l.lang)
    except Exception:  # noqa: BLE001  (BNF7 : la réponse reste affichée en texte)
        log.exception("synthèse")
        wav, note = None, None
    entetes = {"X-Dalila-Lecture": note.encode("ascii", "xmlcharrefreplace").decode()} if note else {}
    return Response(content=wav, media_type="audio/wav", headers=entetes) if wav else Response(status_code=204)


@app.get("/essai", include_in_schema=False)
def essai():
    """Page d'essai locale de la voix et du chat (micro autorisé sur localhost sans HTTPS). DALILA_ESSAI=0 la retire."""
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    if os.environ.get("DALILA_ESSAI", "1") != "1":
        raise HTTPException(404)
    return HTMLResponse((Path(__file__).parent / "essai.html").read_text(encoding="utf-8"))
