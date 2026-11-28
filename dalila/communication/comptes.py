"""Comptes et connexion : l'administrateur de l'AFI se connecte et arrive sur l'administration (/admin/).

POST /auth/connexion     {identifiant, mot_de_passe} -> cookie de session ; {role, nom, suite} (suite : page où aller)
POST /auth/deconnexion   ferme la session (le jeton est effacé de la base)
GET  /auth/moi           le compte connecté, ou 401

Comptes créés en ligne de commande seulement (pas d'inscription publique pour un administrateur) :
    python -m dalila.communication.comptes creer admin --role admin --nom "Agent AFI"   (mot de passe demandé)
    python -m dalila.communication.comptes mot-de-passe admin       (ferme aussi toutes ses sessions)
    python -m dalila.communication.comptes desactiver admin
    python -m dalila.communication.comptes lister

Sécurité :
- mot de passe : empreinte scrypt (N = 2^17, r = 8, p = 1, sel aléatoire de 16 octets), comparaison à temps constant ;
  un identifiant inconnu coûte le même calcul (on ne peut pas deviner les identifiants au temps de réponse) ;
- session : jeton aléatoire de 256 bits, opaque, dans un cookie HttpOnly (illisible par le JavaScript de la page),
  SameSite=Strict, Secure en HTTPS ; la base n'en garde que l'empreinte SHA-256. Le rôle n'est PAS dans le jeton : il est
  relu dans la base à chaque requête. Modifier ou inventer un jeton ne donne donc rien ;
- durée : 8 h au plus, 30 min sans activité ; déconnexion, désactivation ou nouveau mot de passe : sessions fermées ;
- force brute : 5 échecs -> compte bloqué 15 min ; 20 tentatives par adresse en 15 min ; même message d'erreur
  que l'identifiant existe ou non ;
- requêtes forgées depuis un autre site : en plus de SameSite=Strict, toute écriture (POST) doit venir de la page de
  Dalila elle-même (en-tête Origin, sinon Referer, de la même adresse).

Variables (.env) : DALILA_HTTPS=1 (cookie Secure derrière un serveur HTTPS) ; DALILA_PROXY=<adresses> (serveurs
mandataires de confiance, ex. 127.0.0.1 pour Nginx : l'adresse du visiteur est alors lue dans X-Forwarded-For).
"""
import argparse, base64, collections, getpass, hashlib, hmac, os, secrets, sys, threading, time
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from dalila.config import db

ROLES = {"admin": "/admin/"}          # rôle -> page d'arrivée après la connexion
DUREE_MAX, INACTIVITE = 8 * 3600, 30 * 60
ECHECS_MAX, BLOCAGE = 5, 15 * 60
TENTATIVES_PAR_ADRESSE, FENETRE = 20, 15 * 60
LONGUEUR_MIN = 12
N, R, P = 2 ** 17, 8, 1
COOKIE, COOKIE_SECURE = "dalila_session", "__Host-dalila_session"
SURES = {"GET", "HEAD", "OPTIONS"}


# ---------------------------------------------------------------- mots de passe
def empreinte(mot):
    sel = secrets.token_bytes(16)
    h = hashlib.scrypt(mot.encode("utf-8"), salt=sel, n=N, r=R, p=P, maxmem=2 ** 28, dklen=32)
    b = lambda x: base64.b64encode(x).decode("ascii")
    return f"scrypt${N}${R}${P}${b(sel)}${b(h)}"


def verifier(mot, stocke):
    try:
        algo, n, r, p, sel, h = stocke.split("$")
        assert algo == "scrypt"
        calc = hashlib.scrypt(mot.encode("utf-8"), salt=base64.b64decode(sel), n=int(n), r=int(r), p=int(p),
                              maxmem=2 ** 28, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:  # noqa: BLE001  (empreinte illisible : refus)
        return False


_FACTICE = None


def _empreinte_factice():
    """Pour un identifiant inconnu : le même calcul qu'un vrai, pour ne rien révéler par le temps de réponse."""
    global _FACTICE
    if _FACTICE is None:
        _FACTICE = empreinte(secrets.token_urlsafe(16))
    return _FACTICE


def mot_admis(mot, identifiant):
    return len(mot) >= LONGUEUR_MIN and mot.lower() != identifiant.lower()


# ---------------------------------------------------------------- base
def _sql(sql, *p, un=False):
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute(sql, p)
            if sql.lstrip().upper().startswith("SELECT"):
                lignes = cur.fetchall()
                return (lignes[0] if lignes else None) if un else lignes
            return cur.lastrowid or cur.rowcount
    finally:
        con.close()


def _hache(jeton):
    return hashlib.sha256(jeton.encode("ascii")).hexdigest()


def ouvrir_session(compte_id):
    jeton = secrets.token_urlsafe(32)
    _sql("DELETE FROM agent_jetons WHERE compte_id = %s AND (expire_le <= NOW() OR vu_le <= NOW() - INTERVAL %s SECOND)",
         compte_id, INACTIVITE)
    _sql("INSERT INTO agent_jetons (empreinte, compte_id, expire_le) VALUES (%s, %s, NOW() + INTERVAL %s SECOND)",
         _hache(jeton), compte_id, DUREE_MAX)
    return jeton


def compte_de_la_session(jeton):
    """Le compte actif de ce jeton encore valide, ou None. Prolonge l'inactivité (au plus une écriture par minute)."""
    if not jeton or len(jeton) > 100:
        return None
    h = _hache(jeton)
    c = _sql("SELECT c.id, c.identifiant, c.nom, c.role, j.vu_le < NOW() - INTERVAL 60 SECOND a_prolonger "
             "FROM agent_jetons j JOIN agent_comptes c ON c.id = j.compte_id "
             "WHERE j.empreinte = %s AND j.expire_le > NOW() AND j.vu_le > NOW() - INTERVAL %s SECOND "
             "AND c.actif = 1", h, INACTIVITE, un=True)
    if c and c.pop("a_prolonger"):
        _sql("UPDATE agent_jetons SET vu_le = NOW() WHERE empreinte = %s", h)
    return c


def fermer_sessions(compte_id):
    _sql("DELETE FROM agent_jetons WHERE compte_id = %s", compte_id)


# ---------------------------------------------------------------- requêtes
_tentatives, _verrou = collections.defaultdict(collections.deque), threading.Lock()


def adresse(request: Request):
    hote = request.client.host if request.client else ""
    confiance = {a.strip() for a in os.environ.get("DALILA_PROXY", "").split(",") if a.strip()}
    if hote in confiance:   # derrière Nginx : la dernière adresse ajoutée par le mandataire de confiance
        fwd = [a.strip() for a in request.headers.get("x-forwarded-for", "").split(",") if a.strip()]
        if fwd:
            return fwd[-1]
    return hote


def _trop_de_tentatives(ip):
    maintenant = time.monotonic()
    with _verrou:
        d = _tentatives[ip]
        while d and maintenant - d[0] > FENETRE:
            d.popleft()
        if len(d) >= TENTATIVES_PAR_ADRESSE:
            return True
        d.append(maintenant)
        return False


def _https(request):
    return os.environ.get("DALILA_HTTPS", "0") == "1" or request.url.scheme == "https"


def _jeton(request):
    return request.cookies.get(COOKIE_SECURE) or request.cookies.get(COOKIE)


def meme_origine(request: Request):
    """Une écriture doit venir d'une page de Dalila : Origin (sinon Referer) de la même adresse que la requête."""
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return False
    # derrière Nginx : « proxy_set_header Host $host; » garde l'adresse publique dans Host
    return urlsplit(source).netloc.lower() == request.headers.get("host", "").lower()


def exiger(role):
    """Dépendance FastAPI : un compte connecté de ce rôle ; écritures seulement depuis la page de Dalila."""
    def controle(request: Request):
        if request.method not in SURES and not meme_origine(request):
            raise HTTPException(403, "requête refusée : elle ne vient pas de la page de Dalila")
        c = compte_de_la_session(_jeton(request))
        if not c:
            raise HTTPException(401, "connexion nécessaire")
        if c["role"] != role:
            raise HTTPException(403, "ce compte n'a pas accès à cette page")
        return c
    return controle


routeur = APIRouter(prefix="/auth", tags=["connexion"])
REFUS = "identifiant ou mot de passe incorrect"


class Connexion(BaseModel):
    identifiant: str = Field(..., min_length=1, max_length=80)
    mot_de_passe: str = Field(..., min_length=1, max_length=200)


def _sans_cache(response):
    response.headers["Cache-Control"] = "no-store"


@routeur.post("/connexion")
def connexion(c: Connexion, request: Request, response: Response):
    _sans_cache(response)
    if not meme_origine(request):
        raise HTTPException(403, "requête refusée : elle ne vient pas de la page de Dalila")
    if _trop_de_tentatives(adresse(request)):
        raise HTTPException(429, "trop de tentatives : réessayer dans 15 minutes")
    ident = c.identifiant.strip().lower()
    try:
        compte = _sql("SELECT id, identifiant, nom, role, mot_de_passe, actif, bloque_jusqu_a > NOW() bloque "
                      "FROM agent_comptes WHERE identifiant = %s", ident, un=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(503, "service de connexion indisponible")
    ok = verifier(c.mot_de_passe, compte["mot_de_passe"] if compte else _empreinte_factice())
    if not compte or not compte["actif"]:
        raise HTTPException(401, REFUS)
    if compte["bloque"]:
        raise HTTPException(429, "compte bloqué après plusieurs échecs : réessayer dans 15 minutes")
    if not ok:
        # MariaDB évalue SET de gauche à droite : le blocage d'abord, sur l'ancien nombre d'échecs
        _sql("UPDATE agent_comptes SET bloque_jusqu_a = IF(echecs + 1 >= %s, NOW() + INTERVAL %s SECOND, bloque_jusqu_a), "
             "echecs = echecs + 1 WHERE id = %s", ECHECS_MAX, BLOCAGE, compte["id"])
        raise HTTPException(401, REFUS)
    _sql("UPDATE agent_comptes SET echecs = 0, bloque_jusqu_a = NULL, derniere_connexion = NOW() WHERE id = %s",
         compte["id"])
    jeton = ouvrir_session(compte["id"])
    secure = _https(request)
    response.set_cookie(COOKIE_SECURE if secure else COOKIE, jeton, max_age=DUREE_MAX, httponly=True, secure=secure,
                        samesite="strict", path="/")
    return {"identifiant": compte["identifiant"], "nom": compte["nom"], "role": compte["role"],
            "suite": ROLES.get(compte["role"], "/")}


@routeur.post("/deconnexion")
def deconnexion(request: Request, response: Response):
    _sans_cache(response)
    if not meme_origine(request):
        raise HTTPException(403, "requête refusée : elle ne vient pas de la page de Dalila")
    j = _jeton(request)
    if j:
        _sql("DELETE FROM agent_jetons WHERE empreinte = %s", _hache(j))
    for nom in (COOKIE, COOKIE_SECURE):
        response.delete_cookie(nom, path="/", secure=nom == COOKIE_SECURE, httponly=True, samesite="strict")
    return {"ok": True}


@routeur.get("/moi")
def moi(request: Request, response: Response):
    _sans_cache(response)
    c = compte_de_la_session(_jeton(request))
    if not c:
        raise HTTPException(401, "connexion nécessaire")
    return {"identifiant": c["identifiant"], "nom": c["nom"], "role": c["role"], "suite": ROLES.get(c["role"], "/")}


# ---------------------------------------------------------------- ligne de commande
def creer(identifiant, role, mot, nom=None):
    identifiant = identifiant.strip().lower()
    if role not in ROLES:
        raise ValueError(f"rôle inconnu : {role} (rôles : {', '.join(ROLES)})")
    if not mot_admis(mot, identifiant):
        raise ValueError(f"mot de passe trop faible : au moins {LONGUEUR_MIN} caractères, différent de l'identifiant")
    return _sql("INSERT INTO agent_comptes (identifiant, nom, role, mot_de_passe) VALUES (%s, %s, %s, %s)",
                identifiant, nom, role, empreinte(mot))


def changer_mot_de_passe(identifiant, mot):
    identifiant = identifiant.strip().lower()
    if not mot_admis(mot, identifiant):
        raise ValueError(f"mot de passe trop faible : au moins {LONGUEUR_MIN} caractères, différent de l'identifiant")
    c = _sql("SELECT id FROM agent_comptes WHERE identifiant = %s", identifiant, un=True)
    if not c:
        raise ValueError("compte introuvable")
    _sql("UPDATE agent_comptes SET mot_de_passe = %s, mot_de_passe_change_le = NOW(), echecs = 0, bloque_jusqu_a = NULL "
         "WHERE id = %s", empreinte(mot), c["id"])
    fermer_sessions(c["id"])


def desactiver(identifiant):
    c = _sql("SELECT id FROM agent_comptes WHERE identifiant = %s", identifiant.strip().lower(), un=True)
    if not c:
        raise ValueError("compte introuvable")
    _sql("UPDATE agent_comptes SET actif = 0 WHERE id = %s", c["id"])
    fermer_sessions(c["id"])


def _demander_mot():
    """Saisi deux fois sans écho ; DALILA_MOT_DE_PASSE pour un script (jamais dans l'historique du terminal)."""
    if os.environ.get("DALILA_MOT_DE_PASSE"):
        return os.environ["DALILA_MOT_DE_PASSE"]
    a, b = getpass.getpass("Mot de passe : "), getpass.getpass("Encore : ")
    if a != b:
        sys.exit("les deux saisies diffèrent")
    return a


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Comptes de Dalila")
    sous = ap.add_subparsers(dest="action", required=True)
    c = sous.add_parser("creer")
    c.add_argument("identifiant")
    c.add_argument("--role", default="admin", choices=sorted(ROLES))
    c.add_argument("--nom")
    sous.add_parser("mot-de-passe").add_argument("identifiant")
    sous.add_parser("desactiver").add_argument("identifiant")
    sous.add_parser("lister")
    a = ap.parse_args()
    try:
        if a.action == "creer":
            creer(a.identifiant, a.role, _demander_mot(), a.nom)
            print(f"compte « {a.identifiant.lower()} » créé ({a.role})")
        elif a.action == "mot-de-passe":
            changer_mot_de_passe(a.identifiant, _demander_mot())
            print("mot de passe changé ; sessions fermées")
        elif a.action == "desactiver":
            desactiver(a.identifiant)
            print("compte désactivé ; sessions fermées")
        else:
            for r in _sql("SELECT identifiant, nom, role, actif, derniere_connexion FROM agent_comptes ORDER BY id"):
                print(f"{r['identifiant']} | {r['nom'] or ''} | {r['role']} | actif={r['actif']} | "
                      f"dernière connexion {r['derniere_connexion']}")
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
