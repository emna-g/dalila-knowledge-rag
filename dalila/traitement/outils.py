"""Compatibility adapter for the historical fixed pipeline.

All data access and business rules are delegated to the current domain tools.
"""

from dalila.traitement.lots import EntreeLots, chercher_lots
from dalila.traitement.references import codes_gouvernorats_pour_nom
from dalila.traitement.zones import (
    EntreeFiche,
    EntreeListeZones,
    EntreeProximite,
    fiche_zone as lire_fiche_zone,
    lister_zones,
    zones_proches as lire_zones_proches,
)


def _codes(gouvernorat):
    if not gouvernorat:
        return []
    codes = codes_gouvernorats_pour_nom(gouvernorat)
    if not codes:
        raise ValueError(f"Gouvernorat ou région absent du référentiel: {gouvernorat!r}")
    return list(codes)


def _entree_lots(
    gouvernorat=None,
    zone_id=None,
    surface_min=None,
    surface_max=None,
    prix_max_m2=None,
    limite=20,
):
    return EntreeLots(
        gouvernorats=_codes(gouvernorat),
        zones=[str(zone_id)] if zone_id else [],
        surface_min_m2=surface_min,
        surface_max_m2=surface_max,
        prix_max_m2_dt=prix_max_m2,
        limite=limite,
    )


class Outils:
    def chercher_lots(
        self,
        gouvernorat=None,
        zone_id=None,
        surface_min=None,
        surface_max=None,
        prix_max_m2=None,
        limite=20,
    ):
        """Historical row-list shape, backed by the current lot search contract."""
        result = chercher_lots(_entree_lots(
            gouvernorat, zone_id, surface_min, surface_max, prix_max_m2, limite
        ))
        return [{
            "lot_id": lot.lot_id,
            "zone_id": lot.zone_id,
            "zone_fr": lot.zone,
            "lot_num": lot.numero,
            "surface_m2": lot.surface_m2,
            "prix_m2_dt": lot.prix_m2_dt,
            "a_confirmer": lot.a_confirmer,
            "gouvernorat_fr": lot.gouvernorat,
            "prix_terrain_estime_dt": lot.prix_total_dt,
            "prix_selon": lot.prix_selon,
            "prix_dernier_publie_source": lot.prix_dernier_publie_source,
            "prix_dernier_publie_date_source": lot.prix_dernier_publie_date_source,
        } for lot in result.lots]

    def compter_lots(
        self,
        gouvernorat=None,
        zone_id=None,
        surface_min=None,
        surface_max=None,
        prix_max_m2=None,
    ):
        """Return the exact count from the same filters and tariff semantics as chercher_lots."""
        result = chercher_lots(_entree_lots(
            gouvernorat, zone_id, surface_min, surface_max, prix_max_m2, limite=1
        ))
        return result.nombre_total

    def fiche_zone(self, zone_id):
        fiche = lire_fiche_zone(EntreeFiche(zone_id=str(zone_id)))
        if fiche is None:
            return None
        resultat = fiche.model_dump()
        resultat["zone_development_regional"] = resultat["developpement_regional"]
        resultat["gouvernorat_fr"] = resultat["gouvernorat"]
        return resultat

    def zones_proches(self, type_commodite, km_max):
        resultat = lire_zones_proches(EntreeProximite(
            type=type_commodite,
            distance_max_km=km_max,
            seulement_avec_lots_disponibles=False,
        ))
        return [{
            "zone_id": zone.zone_id,
            "nom_fr": zone.nom,
            "gouvernorat_fr": zone.gouvernorat,
            "nom": zone.infrastructure,
            "km": zone.km,
        } for zone in resultat.zones]

    def regime_gouvernorat(self, gouvernorat):
        """Return one regime only when all matching zones with available lots agree."""
        codes = _codes(gouvernorat)
        if not codes:
            return None
        resultat = lister_zones(EntreeListeZones(gouvernorats=codes))
        regimes = {zone.developpement_regional for zone in resultat.zones}
        return {
            frozenset({True}): "developpement_regional",
            frozenset({False}): "littoral",
        }.get(frozenset(regimes))
