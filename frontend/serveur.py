"""Service complet : l'API de Dalila + les données de la carte + l'interface, sur une seule adresse.

    .venv\\Scripts\\python -m uvicorn frontend.serveur:app --host 127.0.0.1 --port 8000
    puis ouvrir http://127.0.0.1:8000/

Reprend l'API du module dalila/communication telle quelle (/carte/chatbot, /carte/voix/..., /sante) et ajoute, en
lecture seule par les vues publiques v_pub_* et le compte dalila_ro (comme les outils de l'agent, jamais les acquéreurs) :

  GET /carte/zones               les zones (position, gouvernorat, prix, lots par état, surfaces des lots disponibles)
  GET /carte/zones/{id}          la fiche d'une zone (distances, équipements, cahiers des charges, plans, services)
  GET /carte/zones/{id}/lots     les lots d'une zone avec leur contour et leur état
  GET /carte/lots/{id}           un lot (pour centrer la carte quand Dalila le cite)

Interface : frontend/app/dist (application de la carte, construite par `npm run build` dans frontend/app) et
frontend/public/dalila (la fenêtre de Dalila seule, à ajouter sur une autre page). Une seule adresse : le micro du
navigateur marche sur http://127.0.0.1 ou en HTTPS.
"""
from collections import defaultdict
from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from dalila.communication.api import app
from dalila.traitement.base import nombre, q

DOSSIER = Path(__file__).parent
_CACHE = {}


def _contour(texte):
    """« lng,lat,0 lng,lat,0 … » (format KML de la base) -> [[lng, lat], …] (ordre GeoJSON)."""
    points = []
    for p in (texte or "").split():
        m = p.split(",")
        if len(m) >= 2:
            try:
                points.append([round(float(m[0]), 7), round(float(m[1]), 7)])
            except ValueError:
                continue
    return points


def _prix(z):
    for k in ("prix_m2_dt", "prix_m2_site_afi_dt", "prix_m2_dernier_publie_dt"):
        if z.get(k) is not None:
            return nombre(z[k])
    return None


def _lot(r):
    return {"lot_id": int(r["lot_id"]), "zone_id": int(r["zone_id"]), "numero": r["lot_num"], "statut": r["statut"],
            "surface_m2": nombre(r.get("surface_m2")),
            "prix_m2_dt": nombre(r["prix_m2_dt"] if r.get("prix_m2_dt") is not None else r.get("prix_m2_dernier_publie_dt")),
            "a_confirmer": bool(r.get("a_confirmer")), "contour": _contour(r.get("coordonnees"))}


SQL_LOTS = ("SELECT p.lot_id, p.zone_id, p.lot_num, p.statut, p.coordonnees, l.surface_m2, l.prix_m2_dt, "
            "l.prix_m2_dernier_publie_dt, l.a_confirmer "
            "FROM v_pub_lot_polygones p LEFT JOIN v_pub_lots l ON l.lot_id = p.lot_id ")


@app.get("/carte/zones")
def zones():
    if "zones" in _CACHE:
        return _CACHE["zones"]
    etats = defaultdict(dict)
    for r in q("SELECT zone_id, statut, COUNT(*) n FROM v_pub_lots GROUP BY zone_id, statut"):
        etats[str(r["zone_id"])][r["statut"]] = r["n"]
    surfaces = {str(r["zone_id"]): r for r in q(
        "SELECT zone_id, MIN(surface_m2) mini, MAX(surface_m2) maxi FROM v_pub_lots "
        "WHERE statut = 'disponible' GROUP BY zone_id")}
    cahiers = {str(r["zone_id"]) for r in q("SELECT DISTINCT zone_id FROM v_pub_cahiers WHERE lien_pdf IS NOT NULL")}
    liste = []
    for z in q("SELECT * FROM v_pub_zones WHERE lat IS NOT NULL AND lng IS NOT NULL ORDER BY nom_fr"):
        s = surfaces.get(str(z["zone_id"]), {})
        liste.append({
            "zone_id": int(z["zone_id"]), "nom": z["nom_fr"], "nom_ar": z["nom_ar"],
            "gouvernorat": z["gouvernorat_fr"], "gouvernorat_ar": z["gouvernorat_ar"],
            "lat": nombre(z["lat"]), "lng": nombre(z["lng"]),
            "prix_m2_dt": _prix(z),
            "prix_m2_subventionne_dt": nombre(z.get("prix_m2_subventionne_site_afi_dt")),
            "surface_totale_m2": nombre(z["surface_totale_m2"]),
            "surface_amenagee_m2": nombre(z["surface_amenagee_m2"]),
            "lots_disponibles": nombre(z["lots_disponibles"]) or 0,
            "lots_a_confirmer": nombre(z["lots_disponibles_a_confirmer"]) or 0,
            "lots_aux_encheres": nombre(z["lots_mis_aux_encheres"]) or 0,
            "lots_par_etat": etats.get(str(z["zone_id"]), {}),
            "surface_lot_min_m2": nombre(s.get("mini")), "surface_lot_max_m2": nombre(s.get("maxi")),
            "developpement_regional": bool(z["zone_developpement_regional"]),
            "groupe_developpement_regional": z.get("groupe_developpement_regional"),
            "cahier_des_charges": str(z["zone_id"]) in cahiers})
    _CACHE["zones"] = liste
    return liste


@app.get("/carte/zones/{zone_id}")
def fiche_zone(zone_id: int):
    z = next((x for x in zones() if x["zone_id"] == zone_id), None)
    if not z:
        raise HTTPException(404, "zone inconnue")
    services = defaultdict(list)
    for r in q("SELECT categorie, nom, distance_km FROM v_pub_services_proches WHERE zone_id = %s "
               "ORDER BY distance_km", str(zone_id)):
        services[r["categorie"]].append({"nom": r["nom"], "km": nombre(r["distance_km"])})
    return {**z,
            "distances": [{"type": r["type"], "nom": r["nom"], "km": nombre(r["km"])} for r in q(
                "SELECT type, nom, km FROM v_pub_zone_distances WHERE zone_id = %s ORDER BY km", str(zone_id))],
            "equipements": [{"type": r["type"], "valeur": r["valeur"], "unite": r["unite"]} for r in q(
                "SELECT type, valeur, unite FROM v_pub_zone_equipements WHERE zone_id = %s", str(zone_id))],
            "cahiers": [{"annee": r["annee"], "lien": r["lien_pdf"], "remarque": r["remarque"]} for r in q(
                "SELECT annee, lien_pdf, remarque FROM v_pub_cahiers WHERE zone_id = %s AND lien_pdf IS NOT NULL",
                str(zone_id))],
            "plans": [{"nom": r["nom"], "lien": r["lien"]} for r in q(
                "SELECT nom, lien FROM v_pub_plans WHERE zone_id = %s AND lien IS NOT NULL", str(zone_id))],
            "services": {k: v[0] for k, v in services.items()}}   # le plus proche de chaque catégorie


@app.get("/carte/zones/{zone_id}/lots")
def lots_de_zone(zone_id: int):
    return [_lot(r) for r in q(SQL_LOTS + "WHERE p.zone_id = %s", str(zone_id))]


@app.get("/carte/lots/{lot_id}")
def lot(lot_id: int):
    r = q(SQL_LOTS + "WHERE p.lot_id = %s", lot_id)
    if not r:
        raise HTTPException(404, "lot inconnu")
    return _lot(r[0])


# en dernier : les fichiers. La fenêtre seule (dalila.js) sous /dalila ; l'application de la carte à la racine.
app.mount("/dalila", StaticFiles(directory=DOSSIER / "public" / "dalila"), name="fenetre")
_APP = DOSSIER / "app" / "dist"
app.mount("/", StaticFiles(directory=_APP if _APP.exists() else DOSSIER / "public", html=True), name="interface")
