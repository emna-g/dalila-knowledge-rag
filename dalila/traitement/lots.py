"""Outil chercher_lots : lots disponibles selon le lieu, la surface, le prix, le budget, le régime et la proximité.

Rend toujours le NOMBRE EXACT de lots (compte en base) et une liste courte, la moins chère d'abord. Les lieux sont donnés
par leurs codes (obtenus avec resoudre_lieu). Un lot d'une zone dont le prix n'est pas publié n'a pas de prix total :
il ne passe pas un filtre de prix ou de budget, et la zone est signalée.
"""
from typing import Literal
from pydantic import BaseModel, Field
from dalila.traitement.base import SOURCE_BASE, Source, nombre, q


class EntreeLots(BaseModel):
    gouvernorats: list[int] = Field(default_factory=list, description="codes des gouvernorats (resoudre_lieu)")
    zones: list[str] = Field(default_factory=list, description="codes des zones (resoudre_lieu)")
    surface_min_m2: float | None = Field(None, ge=0)
    surface_max_m2: float | None = Field(None, ge=0)
    prix_max_m2_dt: float | None = Field(None, ge=0, description="prix au m² maximal, en dinars")
    budget_max_dt: float | None = Field(None, ge=0, description="prix total du terrain maximal (surface × prix au m²)")
    regime: Literal["developpement_regional", "littoral"] | None = None
    groupe_developpement_regional: Literal[1, 2] | None = None
    proche_de: Literal["aeroport", "port", "gare", "autoroute"] | None = None
    distance_max_km: float | None = Field(None, ge=0, description="avec proche_de : distance maximale de la zone")
    tri: Literal["prix_total", "prix_m2", "surface"] = "prix_total"
    limite: int = Field(10, ge=1, le=20, description="nombre de lots à lister (le compte, lui, est toujours exact)")


class Lot(BaseModel):
    lot_id: int
    numero: str
    zone_id: str
    zone: str
    gouvernorat: str
    surface_m2: float
    prix_m2_dt: float | None = Field(description="prix au m² utilisé (actuel, ou dernier publié : voir prix_selon)")
    prix_total_dt: float | None
    prix_selon: str | None = Field(description="« prix actuel de l'AFI », ou dernier prix publié (à confirmer) ; "
                                               "vide : aucun prix publié")
    a_confirmer: bool


class ResultatLots(BaseModel):
    nombre_total: int = Field(description="nombre exact de lots disponibles qui répondent aux filtres")
    lots: list[Lot]
    zones_prix_non_publie: list[str] = Field(description="zones du résultat sans aucun prix publié par l'AFI")
    filtres: dict
    sources: list[Source]


def _zones_retenues(e):
    """Zones qui passent les filtres de lieu, de régime, de groupe et de proximité (50 zones : filtrées en Python)."""
    zones = q("SELECT zone_id, gouvernorat_code, zone_developpement_regional dr, groupe_developpement_regional g "
              "FROM v_pub_zones")
    proches = None
    if e.proche_de:
        proches = {r["zone_id"] for r in q("SELECT zone_id FROM v_pub_zone_distances WHERE type = %s AND km <= %s",
                                           e.proche_de, e.distance_max_km if e.distance_max_km is not None else 1e9)}
    out = []
    for z in zones:
        if (e.gouvernorats or e.zones) and not (z["gouvernorat_code"] in e.gouvernorats or z["zone_id"] in e.zones):
            continue
        if e.regime and z["dr"] != (1 if e.regime == "developpement_regional" else 0):
            continue
        if e.groupe_developpement_regional and z["g"] != e.groupe_developpement_regional:
            continue
        if proches is not None and z["zone_id"] not in proches:
            continue
        out.append(z["zone_id"])
    return out


def chercher_lots(e: EntreeLots) -> ResultatLots:
    # Les zones sont choisies d'abord, puis les lots sont lus dans la seule vue des lots : joindre la vue des zones
    # (qui compte ses lots) ferait tout recalculer pour chaque lot.
    filtres = e.model_dump(exclude_none=True, exclude_defaults=True)
    zones = _zones_retenues(e)
    if not zones:
        return ResultatLots(nombre_total=0, lots=[], zones_prix_non_publie=[], filtres=filtres, sources=[SOURCE_BASE])
    sql = " FROM v_pub_lots_disponibles l WHERE l.zone_id IN (" + ",".join(["%s"] * len(zones)) + ")"
    prix = "COALESCE(l.prix_m2_dt, l.prix_m2_dernier_publie_dt)"  # prix actuel, sinon dernier prix publié par l'AFI
    p = list(zones)
    for cond, val in (("l.surface_m2 >= %s", e.surface_min_m2), ("l.surface_m2 <= %s", e.surface_max_m2),
                      (f"{prix} <= %s", e.prix_max_m2_dt), (f"l.surface_m2 * {prix} <= %s", e.budget_max_dt)):
        if val is not None:
            sql += f" AND {cond}"
            p.append(val)
    par_zone = q(f"SELECT l.zone_id, MAX({prix} IS NULL) sans_prix, COUNT(*) n" + sql + " GROUP BY l.zone_id", *p)
    ordre = {"prix_total": f"{prix} IS NULL, l.surface_m2 * {prix}, l.surface_m2",
             "prix_m2": f"{prix} IS NULL, {prix}, l.surface_m2", "surface": "l.surface_m2"}[e.tri]
    rows = q("SELECT l.lot_id, l.lot_num, l.zone_id, l.zone_fr, l.surface_m2, l.prix_m2_dt, l.prix_m2_dernier_publie_dt, "
             "l.a_confirmer" + sql
             + f" ORDER BY {ordre} LIMIT %s", *p, e.limite)
    gouv = {r["zone_id"]: r["gouvernorat_fr"] for r in q("SELECT zone_id, gouvernorat_fr FROM v_pub_zones")} if rows else {}
    lots = []
    for r in rows:
        pm2 = r["prix_m2_dt"] if r["prix_m2_dt"] is not None else r["prix_m2_dernier_publie_dt"]
        selon = ("prix actuel de l'AFI" if r["prix_m2_dt"] is not None else
                 "dernier prix publié par l'AFI (ancienne carte, 25/11/2026), à confirmer" if pm2 is not None else None)
        lots.append(Lot(lot_id=r["lot_id"], numero=r["lot_num"], zone_id=r["zone_id"], zone=r["zone_fr"],
                        gouvernorat=gouv.get(r["zone_id"], ""), surface_m2=nombre(r["surface_m2"]), prix_m2_dt=nombre(pm2),
                        prix_total_dt=nombre(r["surface_m2"] * pm2) if pm2 is not None else None, prix_selon=selon,
                        a_confirmer=bool(r["a_confirmer"])))
    return ResultatLots(nombre_total=int(sum(r["n"] for r in par_zone)), lots=lots,
                        zones_prix_non_publie=[r["zone_id"] for r in par_zone if r["sans_prix"]],
                        filtres=filtres, sources=[SOURCE_BASE])
