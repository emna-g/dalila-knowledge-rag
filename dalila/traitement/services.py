"""Outil demarche : les 8 services de l'AFI (cahier des charges, IV.6).

    demarche(service=None)              -> la liste des services et du besoin de chacun (pour une question à choix)
    demarche(service="insertion_hypotheque") -> réponses validées de l'AFI, lien, ce que l'AFI ne publie pas, contact

Les textes sont les réponses validées de l'AFI (table chatbot_connaissances, relues à chaque chargement, corrections
appliquées) : conditions, pièces, frais et étapes viennent de là, mot pour mot. Ce que l'AFI ne publie pas
(db/reference/services_afi.csv) est dit tel quel : aucun frais n'est estimé (BF23).
"""
import csv
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel, Field
from dalila.config import RACINE
from dalila.traitement.base import Source, q

Service = Literal["acquisition", "encheres", "situation_fonciere", "insertion_hypotheque", "mainlevee",
                  "acte_precision", "autorisation_vente", "copie_conforme"]
REPONSES_CONTACT = ("kb0026", "kb0003")  # siège, téléphone, formulaire ; numéros corrigés (voir DESACCORDS.md)


class EntreeDemarche(BaseModel):
    service: Service | None = Field(None, description="vide : liste des services pour guider le visiteur")


class ServiceResume(BaseModel):
    service: str
    besoin: str


class Reponse(BaseModel):
    id: str
    question: str
    texte: str


class ResultatDemarche(BaseModel):
    services: list[ServiceResume] = Field(default_factory=list, description="rempli si aucun service n'est demandé")
    service: str | None = None
    reponses_afi: list[Reponse] = Field(default_factory=list)
    lieu_depot: str | None = Field(None, description="où déposer la demande, d'après les réponses de l'AFI")
    non_publie_par_afi: str | None = Field(None, description="à dire tel quel, sans estimation")
    contact_afi: list[Reponse] = Field(default_factory=list)
    sources: list[Source]


@lru_cache(maxsize=1)
def _services():
    with open(RACINE / "db" / "reference" / "services_afi.csv", encoding="utf-8") as fh:
        return {r["service"]: r for r in csv.DictReader(fh)}


def _reponses(ids):
    if not ids:
        return []
    rows = {r["id"]: r for r in q("SELECT id, titre, texte FROM dalila_passages WHERE id IN (" +
                                  ",".join(["%s"] * len(ids)) + ")", *ids)}
    return [Reponse(id=i, question=rows[i]["titre"], texte=rows[i]["texte"]) for i in ids if i in rows]


def demarche(e: EntreeDemarche) -> ResultatDemarche:
    S = _services()
    if e.service is None:
        return ResultatDemarche(services=[ServiceResume(service=k, besoin=v["besoin"]) for k, v in S.items()],
                                sources=[Source(titre="Services de l'AFI", url="https://www.afi.nat.tn/fr/nos-services/")])
    s = S[e.service]
    ids = [f"kb{int(i):04d}" for i in s["reponses_kb"].split(",")]
    return ResultatDemarche(service=e.service, reponses_afi=_reponses(ids), lieu_depot=s["lieu_depot"],
                            non_publie_par_afi=s["non_publie_par_afi"] or None,
                            contact_afi=_reponses(list(REPONSES_CONTACT)),
                            sources=[Source(titre="Base de connaissances de l'AFI (réponses validées)"),
                                     Source(titre="Services de l'AFI", url=s["source"])])
