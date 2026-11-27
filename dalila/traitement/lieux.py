"""Outil resoudre_lieu : un nom de lieu écrit par le visiteur -> zones, gouvernorats ou régions de la base.

    resoudre_lieu("Agba")         -> zone 930403 EL AGBA
    resoudre_lieu("Grand Tunis")  -> région : Tunis, Ariana, Ben Arous, La Manouba
    resoudre_lieu("Jendouba")     -> le gouvernorat (il contient la zone JENDOUBA, proposée en second)

Le modèle extrait le nom de lieu de la question ; cet outil le compare aux noms de la base (français, arabe, anciens noms
des zones) en tolérant les fautes. Il ne devine pas : un nom qui désigne plusieurs lieux est rendu « ambigu », un nom
trop vague (« le sud ») ou inconnu revient vide, et l'agent pose alors une question à choix. Les régions sont seulement
celles que définit une source (db/reference/regions.csv).
"""
import csv, difflib, unicodedata
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel, Field
from dalila.config import RACINE
from dalila.traitement.base import SOURCE_BASE, Source, q

SEUIL = 0.8          # ressemblance minimale pour proposer un lieu
ECART_AMBIGU = 0.05  # deux lieux de natures différentes à moins de cet écart : on ne choisit pas


class EntreeLieu(BaseModel):
    texte: str = Field(..., max_length=100, description="Le nom de lieu tel que le visiteur l'a écrit, sans le reste "
                                                         "de la question (ex. « Agba », « Grand Tunis », « سوسة »).")


class Lieu(BaseModel):
    type: Literal["zone", "gouvernorat", "region"]
    id: str = Field(description="zone : code de la zone ; gouvernorat : code ; région : son nom")
    nom: str
    gouvernorats: list[int] = Field(default_factory=list, description="codes des gouvernorats couverts")
    ressemblance: float


class ResultatLieux(BaseModel):
    texte: str
    lieux: list[Lieu]
    ambigu: bool
    note: str | None = None
    sources: list[Source]


class LieuPossible(BaseModel):
    """Un lieu à proposer au visiteur quand le nom qu'il a écrit est ambigu ou inconnu (question à choix)."""
    type: str
    id: str
    nom: str


def lieu_unique(texte):
    """Pour les outils qui prennent un nom de lieu : (lieu retenu, None) ou (None, lieux à proposer). Jamais deviné."""
    r = resoudre_lieu(EntreeLieu(texte=texte))
    if not r.lieux or r.ambigu:
        return None, [LieuPossible(type=l.type, id=l.id, nom=l.nom) for l in r.lieux]
    return r.lieux[0], None


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.translate(str.maketrans("أإآٱةى", "اااايه"))  # variantes d'écriture des mêmes lettres arabes
    return " ".join("".join(c if c.isalnum() else " " for c in t).split())


@lru_cache(maxsize=1)
def _candidats():
    gouv = {r["code"]: r for r in q("SELECT code, nom_fr, nom_ar FROM dalila_gouvernorats")}
    par_nom = {_norm(g["nom_fr"]): c for c, g in gouv.items()}
    out = []
    for z in q("SELECT zone_id, nom_fr, nom_ar, gouvernorat_code FROM v_pub_zones"):
        noms = [z["nom_fr"], z["nom_ar"]] + [a["alias"] for a in q(
            "SELECT alias FROM dalila_zone_alias WHERE zone_id = %s", z["zone_id"])]
        out.append(("zone", z["zone_id"], z["nom_fr"], [z["gouvernorat_code"]], noms))
    for c, g in gouv.items():
        out.append(("gouvernorat", str(c), g["nom_fr"], [c], [g["nom_fr"], g["nom_ar"]]))
    with open(RACINE / "db" / "reference" / "regions.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            codes = [par_nom[_norm(n)] for n in r["gouvernorats"].split(";")]
            out.append(("region", r["region"], r["region"], codes, [r["region"]]))
    return out


def _ressemblance(qn, nom, contenu=False):
    """contenu=False : le texte est le nom, ou une partie du nom complet (« Agba » / « EL AGBA ») ;
    contenu=True : le texte contient le nom avec d'autres mots (« ولاية جندوبة »), utilisé seulement si rien d'autre."""
    n = _norm(nom)
    if not n:
        return 0.0
    mq, mn = qn.split(), n.split()
    if contenu:
        return max([difflib.SequenceMatcher(None, n, " ".join(mq[i:i + len(mn)])).ratio()
                    for i in range(len(mq) - len(mn) + 1)] or [0.0])
    best = difflib.SequenceMatcher(None, qn, n).ratio()
    for i in range(len(mn) - len(mq) + 1):
        best = max(best, difflib.SequenceMatcher(None, qn, " ".join(mn[i:i + len(mq)])).ratio())
    return best


def resoudre_lieu(e: EntreeLieu) -> ResultatLieux:
    qn = _norm(e.texte)
    trouves = []
    for contenu in (False, True):
        for typ, ident, nom, gouvs, noms in _candidats():
            s = max(_ressemblance(qn, n, contenu) for n in noms)
            if s >= SEUIL:
                trouves.append(Lieu(type=typ, id=ident, nom=nom, gouvernorats=gouvs, ressemblance=round(s, 2)))
        if trouves:
            break
    trouves.sort(key=lambda l: -l.ressemblance)
    if not trouves:
        return ResultatLieux(texte=e.texte, lieux=[], ambigu=False, sources=[SOURCE_BASE],
                             note="Lieu inconnu ou trop vague : demander au visiteur de choisir un gouvernorat ou une zone.")
    haut = trouves[0].ressemblance
    proches = [l for l in trouves if l.ressemblance >= haut - ECART_AMBIGU]
    ambigu = len({(l.type, l.id) for l in proches}) > 1
    note = None
    gouv = [l for l in proches if l.type in ("gouvernorat", "region")]
    if ambigu and len(gouv) == 1 and all(set(l.gouvernorats) <= set(gouv[0].gouvernorats) for l in proches):
        # « Jendouba » : le gouvernorat contient la zone du même nom -> chercher dans le gouvernorat, proposer la zone
        zones = [l for l in proches if l is not gouv[0]]
        return ResultatLieux(texte=e.texte, lieux=[gouv[0]] + zones[:5], ambigu=False, sources=[SOURCE_BASE],
                             note=f"Le {gouv[0].type} {gouv[0].nom} contient la ou les zones du même nom : chercher dans "
                                  f"le {gouv[0].type} (premier lieu) et proposer la zone en question à choix.")
    if ambigu:
        types = {l.type for l in proches}
        note = ("Le même nom désigne " + " et ".join(sorted(types)) + " : choisir selon la question (un gouvernorat couvre "
                "ses zones) ou demander au visiteur." if len(types) > 1 else
                "Plusieurs lieux portent un nom proche : demander au visiteur lequel.")
    return ResultatLieux(texte=e.texte, lieux=proches[:6], ambigu=ambigu, note=note, sources=[SOURCE_BASE])
