"""Outil chercher_lots : lots disponibles selon le lieu, la surface, le tarif de zone, le budget et la proximité.

Rend toujours le NOMBRE EXACT de lots (compte en base) et une liste courte, la moins chère d'abord. Le prix au m² vient
de la zone et le total calculé est une estimation, pas un prix propre au lot. Sans tarif publié, le total reste nul et
le lot ne passe pas un filtre de prix ou de budget.
"""
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from dalila.traitement.base import SOURCE_BASE, Source, nombre, q
from dalila.traitement.references import (
    groupe_developpement_regional,
    nom_gouvernorat,
)


class EntreeLots(BaseModel):
    gouvernorats: list[int] = Field(default_factory=list, description="codes des gouvernorats (resoudre_lieu)")
    zones: list[str] = Field(default_factory=list, description="codes des zones (resoudre_lieu)")
    surface_min_m2: float | None = Field(None, ge=0)
    surface_max_m2: float | None = Field(None, ge=0)
    prix_max_m2_dt: float | None = Field(None, ge=0, description="tarif de zone maximal au m², en dinars")
    budget_max_dt: float | None = Field(
        None, ge=0, description="budget estimatif maximal (surface du lot × tarif au m² de la zone)"
    )
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
    gouvernorat: str | None = Field(description="nom du gouvernorat du référentiel, nul si le code est inconnu")
    surface_m2: float
    prix_m2_dt: float | None = Field(
        description="tarif au m² de la zone, pas un prix propre au lot; voir prix_selon"
    )
    prix_total_dt: float | None = Field(
        description="estimation surface du lot × tarif de zone, pas un prix final publié pour ce lot"
    )
    prix_dernier_publie_source: str | None = None
    prix_dernier_publie_date_source: date | None = None
    prix_selon: str | None = Field(
        description="origine du tarif de zone utilisé; vide si aucun tarif de zone n'est publié"
    )
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
              "FROM v_pub_zones_v2")
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
        groupe = groupe_developpement_regional(z["zone_id"], z["dr"])
        if z["g"] is not None and int(z["g"]) != groupe:
            raise ValueError(f"Divergence de groupe de développement régional pour la zone {z['zone_id']}")
        if e.groupe_developpement_regional and groupe != e.groupe_developpement_regional:
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
    prix = "COALESCE(l.prix_m2_dt, l.prix_m2_dernier_publie_dt)"
    sql = (
        " FROM v_pub_lots_disponibles_v2 l WHERE l.zone_id IN ("
        + ",".join(["%s"] * len(zones)) + ")"
    )
    p = list(zones)
    for cond, val in (("l.surface_m2 >= %s", e.surface_min_m2), ("l.surface_m2 <= %s", e.surface_max_m2),
                      (f"{prix} <= %s", e.prix_max_m2_dt), (f"l.surface_m2 * {prix} <= %s", e.budget_max_dt)):
        if val is not None:
            sql += f" AND {cond}"
            p.append(val)
    par_zone = q(f"SELECT l.zone_id, MAX({prix} IS NULL) sans_prix, COUNT(*) n" + sql + " GROUP BY l.zone_id", *p)
    ordre = {"prix_total": f"{prix} IS NULL, l.surface_m2 * {prix}, l.surface_m2",
             "prix_m2": f"{prix} IS NULL, {prix}, l.surface_m2", "surface": "l.surface_m2"}[e.tri]
    rows = q(
        "SELECT l.lot_id, l.lot_num, l.zone_id, l.zone_fr, l.surface_m2, l.prix_m2_dt, "
        "l.prix_m2_dernier_publie_dt, l.prix_dernier_publie_source, "
        "l.prix_dernier_publie_date_source, l.a_confirmer" + sql
        + f" ORDER BY {ordre} LIMIT %s",
        *p, e.limite,
    )
    gouv = {}
    if rows:
        for r in q("SELECT zone_id, gouvernorat_code FROM v_pub_zones_v2"):
            code = r["gouvernorat_code"]
            gouv[r["zone_id"]] = nom_gouvernorat(code)
    lots = []
    for r in rows:
        pm2 = r["prix_m2_dt"] if r["prix_m2_dt"] is not None else r["prix_m2_dernier_publie_dt"]
        selon = ("tarif actuel au m² de la zone, publié par l'AFI; total estimatif" if r["prix_m2_dt"] is not None else
                 "dernier prix publié de la zone, à confirmer; total estimatif"
                 if pm2 is not None else None)
        lots.append(Lot(lot_id=r["lot_id"], numero=r["lot_num"], zone_id=r["zone_id"], zone=r["zone_fr"],
                        gouvernorat=gouv.get(r["zone_id"]), surface_m2=nombre(r["surface_m2"]), prix_m2_dt=nombre(pm2),
                        prix_total_dt=nombre(r["surface_m2"] * pm2) if pm2 is not None else None, prix_selon=selon,
                        prix_dernier_publie_source=(
                            r.get("prix_dernier_publie_source") if r["prix_m2_dt"] is None else None
                        ),
                        prix_dernier_publie_date_source=(
                            r.get("prix_dernier_publie_date_source") if r["prix_m2_dt"] is None else None
                        ),
                        a_confirmer=bool(r["a_confirmer"])))
    sources_prix = {}
    for row in rows:
        source = row.get("prix_dernier_publie_source")
        if source and row["prix_m2_dt"] is None:
            date_source = row.get("prix_dernier_publie_date_source")
            sources_prix[(source, date_source)] = Source(titre=source, date_source=date_source)
    return ResultatLots(nombre_total=int(sum(r["n"] for r in par_zone)), lots=lots,
                        zones_prix_non_publie=[r["zone_id"] for r in par_zone if r["sans_prix"]],
                        filtres=filtres, sources=[SOURCE_BASE, *sources_prix.values()])
