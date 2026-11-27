"""Registre des outils de l'agent : la liste FERMÉE de ce que l'agent peut faire.

    from dalila.traitement.registre import definitions, appeler
    definitions()                                   -> descriptions et schémas JSON, au format des appels d'outils d'Ollama
    appeler("chercher_lots", {"gouvernorats": [8]}) -> résultat (dict JSON), ou {"erreur": ...}

Un outil absent du registre ne peut pas être appelé. Les arguments sont validés (types, bornes) avant toute requête ;
une erreur est rendue comme un message court, jamais comme une exception brute (BNF4). Tous les outils sont en lecture
seule (compte dalila_ro). Ajouter un outil : l'écrire dans ce dossier, puis l'ajouter à OUTILS.
"""
from pydantic import ValidationError
from dalila.traitement.graphe import EntreeConcepts, EntreeConseil, conseiller, relier_concepts
from dalila.traitement.lieux import EntreeLieu, resoudre_lieu
from dalila.traitement.lots import EntreeLots, chercher_lots
from dalila.traitement.passages import EntreePassages, chercher_passages
from dalila.traitement.services import EntreeDemarche, demarche
from dalila.traitement.zones import (EntreeFiche, EntreeListeZones, EntreeProximite, fiche_zone, lister_zones,
                                     zones_proches)

OUTILS = {
    # ---- graphe de connaissances : comprendre et raisonner (aucun chiffre)
    "relier_concepts": (relier_concepts, EntreeConcepts,
                        "Relie les mots de la question (toutes langues, tunisien et arabizi compris) aux concepts de "
                        "l'ontologie : lieux, lots, secteurs, commodités, démarches, incitations, organismes, services de "
                        "l'AFI. Donne aussi les services reconnus, à passer à l'outil demarche."),
    "conseiller": (conseiller, EntreeConseil,
                   "Pour un projet décrit avec les mots du visiteur : activités de la nomenclature les plus proches par "
                   "le sens, secteur, organismes compétents avec leur rôle (seuils d'investissement), infrastructures "
                   "utiles (à passer à zones_proches) et raccordements nécessaires, avec l'explication de chaque lien. "
                   "Ne rien ajouter que le graphe ne donne pas."),
    # ---- base MariaDB : chiffres (vues v_pub_*) et textes à citer
    "resoudre_lieu": (resoudre_lieu, EntreeLieu,
                      "Trouve la zone, le gouvernorat ou la région correspondant à un nom de lieu écrit par le visiteur "
                      "(fautes tolérées, français ou arabe). Si le résultat est ambigu ou vide, poser une question à "
                      "choix au visiteur. Utilisé à l'intérieur des autres outils ; le harnais ne le montre pas au "
                      "modèle (une étape de moins)."),
    "chercher_lots": (chercher_lots, EntreeLots,
                      "Lots disponibles selon le lieu (son nom tel qu'écrit par le visiteur, dans le champ lieu), la "
                      "surface, le prix au m², le budget total, le régime, le groupe de développement régional et la "
                      "proximité d'un aéroport, port, gare ou autoroute. Donne le nombre exact et les lots les moins chers ; "
                      "si le lieu est ambigu, rend les lieux à proposer au visiteur."),
    "fiche_zone": (fiche_zone, EntreeFiche,
                   "Tout sur une zone : prix, surfaces, lots disponibles, régime et groupe, distances, équipements, "
                   "services proches, cahier des charges et plan de lotissement (liens)."),
    "lister_zones": (lister_zones, EntreeListeZones,
                     "Zones d'un lieu (gouvernorat ou région, son nom tel qu'écrit par le visiteur, dans le champ lieu), "
                     "d'un régime ou d'un groupe, avec leurs lots disponibles et leur prix."),
    "zones_proches": (zones_proches, EntreeProximite,
                      "Zones les plus proches d'un aéroport, port, gare, autoroute ou gazoduc, avec la distance."),
    "demarche": (demarche, EntreeDemarche,
                 "Services de l'AFI : sans service, la liste pour guider le visiteur par une question à choix ; avec un "
                 "service, conditions, pièces, frais, étapes et lien (réponses validées de l'AFI) et contact de l'AFI."),
    "chercher_passages": (chercher_passages, EntreePassages,
                          "Textes officiels à citer avec leur lien : cahier des charges d'une zone (activités autorisées, "
                          "règles de construction), incitations, lois, sites officiels (TIA, FIPA, APII, APIA, SICAD)."),
}


def definitions():
    """Les outils au format des appels d'outils (Ollama / OpenAI) : nom, description, schéma JSON des arguments."""
    return [{"type": "function", "function": {"name": nom, "description": desc,
                                              "parameters": modele.model_json_schema()}}
            for nom, (_, modele, desc) in OUTILS.items()]


def appeler(nom, arguments):
    """Appelle un outil du registre avec des arguments validés ; rend un dict JSON."""
    if nom not in OUTILS:
        return {"erreur": f"outil inconnu : {nom}"}
    fonction, modele, _ = OUTILS[nom]
    try:
        entree = modele.model_validate(arguments or {})
    except ValidationError as ex:
        return {"erreur": "arguments invalides", "details": [f"{'.'.join(map(str, e['loc']))} : {e['msg']}"
                                                             for e in ex.errors()]}
    try:
        res = fonction(entree)
    except Exception as ex:  # noqa: BLE001  (aucune exception brute ne remonte à l'agent)
        return {"erreur": f"l'outil {nom} n'a pas pu répondre ({type(ex).__name__})"}
    return {"resultat": None} if res is None else res.model_dump(mode="json")
