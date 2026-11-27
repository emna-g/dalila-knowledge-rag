"""Read-only map projections from the AFI SQL views and lot KML contours."""

import math
from typing import Any, Dict, List, Optional

from shapely.geometry import Polygon, mapping

from dalila.traitement.base import nombre, q
from dalila.traitement.references import groupe_developpement_regional, nom_gouvernorat


_AVERTISSEMENT_CONTOURS = (
    "Contours issus de lots_kml via les vues publiques AFI. "
    "Les statuts et la disponibilité actuelle des lots restent inconnus."
)


def _coord(value: Any, minimum: float, maximum: float) -> Optional[float]:
    try:
        number_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number_value) or not minimum <= number_value <= maximum:
        return None
    return number_value


def _geojson_polygon(coordinates: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(coordinates, str):
        return None

    points = []
    try:
        for token in coordinates.split():
            parts = token.split(",")
            if len(parts) < 2:
                return None
            longitude = _coord(parts[0], -180, 180)
            latitude = _coord(parts[1], -90, 90)
            if longitude is None or latitude is None:
                return None
            points.append((longitude, latitude))
    except (OverflowError, ValueError):
        return None

    if len(points) < 4 or points[0] != points[-1]:
        return None

    polygon = Polygon(points)
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        return None
    return mapping(polygon)


def lister_zones_carte() -> Dict[str, Any]:
    rows = q(
        "SELECT zone_id, nom_fr, nom_ar, gouvernorat_code, lat, lng, "
        "zone_developpement_regional, groupe_developpement_regional "
        "FROM v_pub_zones ORDER BY nom_fr"
    )
    zones = []
    for row in rows:
        code = row.get("gouvernorat_code")
        groupe = groupe_developpement_regional(
            row["zone_id"], row.get("zone_developpement_regional")
        )
        groupe_vue = row.get("groupe_developpement_regional")
        if groupe_vue is not None and int(groupe_vue) != groupe:
            raise ValueError(
                f"Divergence de groupe de développement régional pour la zone {row['zone_id']}"
            )
        zones.append({
            "zone_id": str(row["zone_id"]),
            "name_fr": row.get("nom_fr"),
            "name_ar": row.get("nom_ar"),
            "governorate_fr": nom_gouvernorat(code),
            "governorate_code": str(code) if code is not None else None,
            "development_regional": (
                bool(row["zone_developpement_regional"])
                if row.get("zone_developpement_regional") is not None else None
            ),
            "development_regional_group": groupe,
            "latitude": _coord(row.get("lat"), -90, 90),
            "longitude": _coord(row.get("lng"), -180, 180),
            "source_id": "afi_sql",
        })
    zones.sort(key=lambda zone: (
        zone["governorate_fr"] or "",
        zone["name_fr"] or "",
        zone["zone_id"],
    ))
    return {
        "source_id": "afi_sql",
        "zones": zones,
    }


def lots_carte(zone_id: str, limit: int = 500, after_lot_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if not q("SELECT zone_id FROM v_pub_zones WHERE zone_id = %s", zone_id):
        return None

    sql = (
        "SELECT p.lot_id, p.zone_id, p.lot_num, p.coordonnees, l.surface_m2 "
        "FROM v_pub_lot_polygones p JOIN v_pub_lots l ON l.lot_id = p.lot_id "
        "WHERE p.zone_id = %s"
    )
    parameters: List[Any] = [zone_id]
    if after_lot_id is not None:
        sql += " AND p.lot_id > %s"
        parameters.append(after_lot_id)
    sql += " ORDER BY p.lot_id LIMIT %s"
    parameters.append(limit + 1)

    rows = q(sql, *parameters)
    truncated = len(rows) > limit
    page = rows[:limit]
    features = []
    rejected_geometry_count = 0
    for row in page:
        geometry = _geojson_polygon(row.get("coordonnees"))
        if geometry is None:
            rejected_geometry_count += 1
            continue
        lot_number = str(row["lot_num"]).strip() if row.get("lot_num") is not None else None
        features.append({
            "type": "Feature",
            "id": str(row["lot_id"]),
            "geometry": geometry,
            "properties": {
                "zone_id": str(row["zone_id"]),
                "lot_id": str(row["lot_id"]),
                "lot_number": lot_number or None,
                "area_m2_raw": nombre(row.get("surface_m2")),
                "availability_state": "unknown",
                "status_requires_afi_confirmation": True,
                "source_id": "afi_sql_kml",
            },
        })

    return {
        "type": "FeatureCollection",
        "source_id": "afi_sql_kml",
        "notice": _AVERTISSEMENT_CONTOURS,
        "features": features,
        "truncated": truncated,
        "next_cursor": int(page[-1]["lot_id"]) if truncated and page else None,
        "rejected_geometry_count": rejected_geometry_count,
    }
