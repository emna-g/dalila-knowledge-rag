"""Canonical, validated reference data shared by DALILA's runtime and loaders."""

import csv
import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from dalila.config import RACINE

REF = RACINE / "db" / "reference"
CORR = RACINE / "db" / "corrections"
CODES_GOUVERNORATS_ATTENDUS = frozenset(range(1, 25))
_DATE_SOURCE = re.compile(r"\b(?:relev[ée]e?|lue)\s+le\s+(\d{4}-\d{2}-\d{2})\b", re.I)


def _lire_csv(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier))


def normaliser_nom_lieu(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "").lower())
    texte = "".join(caractere for caractere in texte if not unicodedata.combining(caractere))
    texte = texte.translate(str.maketrans("أإآٱةى", "اااايه"))
    return " ".join("".join(c if c.isalnum() else " " for c in texte).split())


@lru_cache(maxsize=1)
def gouvernorats_par_code() -> dict[int, dict[str, str]]:
    resultat = {}
    for ligne in _lire_csv(REF / "gouvernorats.csv"):
        try:
            code = int(ligne["code"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Code de gouvernorat invalide dans gouvernorats.csv") from exc
        nom_fr = (ligne.get("nom_fr") or "").strip()
        nom_ar = (ligne.get("nom_ar") or "").strip()
        if code not in CODES_GOUVERNORATS_ATTENDUS or code in resultat or not nom_fr or not nom_ar:
            raise ValueError(f"Référentiel gouvernorats.csv invalide pour le code {code}")
        resultat[code] = {"nom_fr": nom_fr, "nom_ar": nom_ar}
        source = (ligne.get("source") or "").strip()
        if source:
            resultat[code]["source"] = source
    return resultat


def gouvernorats_absents() -> tuple[int, ...]:
    return tuple(sorted(CODES_GOUVERNORATS_ATTENDUS - gouvernorats_par_code().keys()))


def nom_gouvernorat(code, langue="fr"):
    if code is None or langue not in ("fr", "ar"):
        return None
    try:
        valeurs = gouvernorats_par_code().get(int(code))
    except (TypeError, ValueError):
        return None
    return valeurs.get(f"nom_{langue}") if valeurs else None


@lru_cache(maxsize=1)
def regions() -> tuple[dict[str, object], ...]:
    codes_fr = {
        normaliser_nom_lieu(valeurs["nom_fr"]): code
        for code, valeurs in gouvernorats_par_code().items()
    }
    resultat = []
    noms_vus = set()
    for ligne in _lire_csv(REF / "regions.csv"):
        nom = (ligne.get("region") or "").strip()
        source = (ligne.get("source") or "").strip()
        cle = normaliser_nom_lieu(nom)
        if not nom or not source or not cle or cle in noms_vus:
            raise ValueError(f"Référentiel regions.csv invalide pour {nom!r}")
        codes = []
        for nom_gouvernorat in (ligne.get("gouvernorats") or "").split(";"):
            code = codes_fr.get(normaliser_nom_lieu(nom_gouvernorat))
            if code is None:
                raise ValueError(
                    f"Gouvernorat {nom_gouvernorat!r} de regions.csv absent de gouvernorats.csv"
                )
            if code in codes:
                raise ValueError(f"Gouvernorat dupliqué dans la région {nom!r}")
            codes.append(code)
        if not codes:
            raise ValueError(f"Région sans gouvernorat dans regions.csv: {nom!r}")
        noms_vus.add(cle)
        resultat.append({"region": nom, "gouvernorats": tuple(codes), "source": source})
    return tuple(resultat)


@lru_cache(maxsize=1)
def regions_par_nom() -> dict[str, tuple[int, ...]]:
    return {
        normaliser_nom_lieu(ligne["region"]): ligne["gouvernorats"]
        for ligne in regions()
    }


def codes_gouvernorats_pour_nom(nom: str) -> tuple[int, ...]:
    """Resolve an exact or uniquely contained FR/AR name or region; never guess ambiguities."""
    recherche = normaliser_nom_lieu(nom)
    if not recherche:
        return ()

    gouvernorats = gouvernorats_par_code()
    correspondances_exactes = {
        code
        for code, valeurs in gouvernorats.items()
        if recherche in {
            normaliser_nom_lieu(valeurs["nom_fr"]),
            normaliser_nom_lieu(valeurs["nom_ar"]),
        }
    }
    if correspondances_exactes:
        return tuple(sorted(correspondances_exactes))

    region = regions_par_nom().get(recherche)
    if region is not None:
        return region

    correspondances = set()
    for code, valeurs in gouvernorats.items():
        noms = (valeurs["nom_fr"], valeurs["nom_ar"])
        if any(recherche in normaliser_nom_lieu(nom) for nom in noms):
            correspondances.add(code)
    if len(correspondances) > 1:
        raise ValueError(f"Nom de lieu ambigu dans le référentiel: {nom!r}")
    return tuple(correspondances)


@lru_cache(maxsize=1)
def alias_zones() -> tuple[dict[str, str], ...]:
    resultat = []
    vus = set()
    for ligne in _lire_csv(CORR / "alias_zones.csv"):
        zone_id = (ligne.get("zone_id") or "").strip()
        alias = (ligne.get("alias") or "").strip()
        langue = (ligne.get("langue") or "").strip()
        source = (ligne.get("source") or "").strip()
        cle = (zone_id, alias)
        if not all((zone_id, alias, source)) or langue not in ("fr", "ar") or cle in vus:
            raise ValueError(f"Référentiel alias_zones.csv invalide pour {cle}")
        vus.add(cle)
        resultat.append({"zone_id": zone_id, "alias": alias, "langue": langue, "source": source})
    return tuple(resultat)


@lru_cache(maxsize=1)
def alias_zones_par_id() -> dict[str, tuple[str, ...]]:
    resultat = defaultdict(list)
    for ligne in alias_zones():
        resultat[ligne["zone_id"]].append(ligne["alias"])
    return {zone_id: tuple(alias) for zone_id, alias in resultat.items()}


@lru_cache(maxsize=1)
def groupes_developpement_regional_par_zone() -> dict[str, dict[str, object]]:
    resultat = {}
    for ligne in _lire_csv(REF / "groupes_developpement_regional.csv"):
        zone_id = (ligne.get("zone_id") or "").strip()
        delegation = (ligne.get("delegation") or "").strip()
        source = (ligne.get("source") or "").strip()
        try:
            groupe = int(ligne["groupe"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Groupe invalide pour la zone {zone_id!r}") from exc
        if not zone_id or not delegation or not source or groupe not in (1, 2) or zone_id in resultat:
            raise ValueError(f"Référentiel groupes_developpement_regional.csv invalide pour {zone_id!r}")
        resultat[zone_id] = {"groupe": groupe, "delegation": delegation, "source": source}
    return resultat


def groupe_developpement_regional(zone_id, indicateur):
    """Return a sourced group only when AFI marks the zone as regional."""
    if indicateur is None or int(indicateur) != 1:
        return None
    reference = groupes_developpement_regional_par_zone().get(str(zone_id))
    return reference["groupe"] if reference else None


def _date_source(source):
    correspondance = _DATE_SOURCE.search(source or "")
    if not correspondance:
        return None
    try:
        return date.fromisoformat(correspondance.group(1))
    except ValueError as exc:
        raise ValueError(f"Date de source invalide: {correspondance.group(1)}") from exc


def _prix_decimal(valeur, zone_id, fichier):
    try:
        prix = Decimal(valeur)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Prix invalide pour la zone {zone_id!r} dans {fichier}") from exc
    if not prix.is_finite() or prix < 0:
        raise ValueError(f"Prix invalide pour la zone {zone_id!r} dans {fichier}")
    return prix


@lru_cache(maxsize=1)
def derniers_prix_publies_par_zone() -> dict[str, dict[str, object]]:
    resultat = {}
    fichier = "derniers_prix_publies.csv"
    for ligne in _lire_csv(REF / fichier):
        zone_id = (ligne.get("zone_id") or "").strip()
        source = (ligne.get("source") or "").strip()
        if not zone_id or not source or zone_id in resultat:
            raise ValueError(f"Référentiel {fichier} invalide pour la zone {zone_id!r}")
        resultat[zone_id] = {
            "prix_m2_dt": _prix_decimal(ligne.get("prix_m2_dt"), zone_id, fichier),
            "source": source,
            "date_source": _date_source(source),
        }
    return resultat


@lru_cache(maxsize=1)
def prix_site_afi_par_zone() -> dict[str, dict[str, object]]:
    resultat = {}
    fichier = "prix_site_afi.csv"
    for ligne in _lire_csv(REF / fichier):
        zone_id = (ligne.get("zone_id") or "").strip()
        source = (ligne.get("source") or "").strip()
        nom = (ligne.get("nom_sur_la_page") or "").strip()
        if not zone_id or not source or not nom or zone_id in resultat:
            raise ValueError(f"Référentiel {fichier} invalide pour la zone {zone_id!r}")
        resultat[zone_id] = {
            "nom_sur_la_page": nom,
            "prix_m2_dt": _prix_decimal(ligne.get("prix_m2_dt"), zone_id, fichier),
            "prix_m2_subventionne_dt": _prix_decimal(
                ligne.get("prix_m2_subventionne_dt"), zone_id, fichier
            ),
            "source": source,
            "date_source": _date_source(source),
        }
    return resultat
