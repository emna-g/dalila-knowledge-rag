"""Outil resoudre_lieu : un nom de lieu écrit par le visiteur -> zones, gouvernorats ou régions de la base.

    resoudre_lieu("Agba")         -> zone 930403 EL AGBA
    resoudre_lieu("Grand Tunis")  -> région : Tunis, Ariana, Ben Arous, La Manouba
    resoudre_lieu("Jendouba")     -> ambigu : le gouvernorat ET la zone JENDOUBA

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


def _ressemblance(qn, nom):
    n = _norm(nom)
    if not n:
        return 0.0
    best = difflib.SequenceMatcher(None, qn, n).ratio()
    mq, mn = qn.split(), n.split()
    for i in range(len(mn) - len(mq) + 1):  # le nom cherché peut être une partie du nom complet (« Agba » / « EL AGBA »)
        best = max(best, difflib.SequenceMatcher(None, qn, " ".join(mn[i:i + len(mq)])).ratio())
    return best


def resoudre_lieu(e: EntreeLieu) -> ResultatLieux:
    qn = _norm(e.texte)
    trouves = []
    for typ, ident, nom, gouvs, noms in _candidats():
        s = max(_ressemblance(qn, n) for n in noms)
        if s >= SEUIL:
            trouves.append(Lieu(type=typ, id=ident, nom=nom, gouvernorats=gouvs, ressemblance=round(s, 2)))
    trouves.sort(key=lambda l: -l.ressemblance)
    if not trouves:
        return ResultatLieux(texte=e.texte, lieux=[], ambigu=False, sources=[SOURCE_BASE],
                             note="Lieu inconnu ou trop vague : demander au visiteur de choisir un gouvernorat ou une zone.")
    haut = trouves[0].ressemblance
    proches = [l for l in trouves if l.ressemblance >= haut - ECART_AMBIGU]
    ambigu = len({(l.type, l.id) for l in proches}) > 1
    note = None
    if ambigu:
        types = {l.type for l in proches}
        note = ("Le même nom désigne " + " et ".join(sorted(types)) + " : choisir selon la question (un gouvernorat couvre "
                "ses zones) ou demander au visiteur." if len(types) > 1 else
                "Plusieurs lieux portent un nom proche : demander au visiteur lequel.")
    return ResultatLieux(texte=e.texte, lieux=proches[:6], ambigu=ambigu, note=note, sources=[SOURCE_BASE])
