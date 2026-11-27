"""Outils chiffrés de Dalila : tout est lu dans les vues v_pub_* de MariaDB (compte lecture seule dalila_ro).
Aucun chiffre n'est inventé : chaque résultat est une ligne de la base, avec sa source.

    from dalila.traitement.outils import Outils
    o = Outils()
    o.chercher_lots(gouvernorat="Sfax")          # lots disponibles, du moins cher au plus cher
    o.fiche_zone("930508")                       # prix, lots, distances, équipements, services proches, cahier
    o.zones_proches("port", km_max=20)
"""
from dalila.config import db


class Outils:
    def __init__(self):
        self.con = db("ro")

    def _q(self, sql, *p):
        with self.con.cursor() as cur:
            cur.execute(sql, p)
            return cur.fetchall()

    @staticmethod
    def _filtres_lots(gouvernorat=None, zone_id=None, surface_min=None, surface_max=None, prix_max_m2=None):
        """Filtres communs à chercher_lots et compter_lots : les deux voient toujours les mêmes lots."""
        sql = " FROM v_pub_lots_disponibles l JOIN v_pub_zones z USING (zone_id) WHERE 1=1"
        p = []
        if gouvernorat:
            sql += " AND (z.gouvernorat_fr LIKE %s OR z.gouvernorat_ar LIKE %s)"
            p += [f"%{gouvernorat}%"] * 2
        if zone_id:
            sql += " AND l.zone_id = %s"
            p.append(str(zone_id))
        if surface_min:
            sql += " AND l.surface_m2 >= %s"
            p.append(surface_min)
        if surface_max:
            sql += " AND l.surface_m2 <= %s"
            p.append(surface_max)
        if prix_max_m2:
            sql += " AND l.prix_m2_dt <= %s"
            p.append(prix_max_m2)
        return sql, p

    def chercher_lots(self, gouvernorat=None, zone_id=None, surface_min=None, surface_max=None, prix_max_m2=None,
                      limite=20):
        """Liste (limitée à `limite` lignes) des lots disponibles, du moins cher au plus cher. Pour un NOMBRE de lots,
        utiliser compter_lots : la longueur de cette liste n'est pas un compte."""
        filtres, p = self._filtres_lots(gouvernorat, zone_id, surface_min, surface_max, prix_max_m2)
        sql = ("SELECT l.lot_id, l.zone_id, l.zone_fr, l.lot_num, l.surface_m2, l.prix_m2_dt, l.a_confirmer, "
               "z.gouvernorat_fr, l.surface_m2 * l.prix_m2_dt AS prix_terrain_estime_dt" + filtres +
               " ORDER BY l.prix_m2_dt IS NULL, l.prix_m2_dt, l.surface_m2 LIMIT %s")
        return self._q(sql, *p, limite)

    def compter_lots(self, gouvernorat=None, zone_id=None, surface_min=None, surface_max=None, prix_max_m2=None):
        """Nombre de lots disponibles (COUNT dans la vue), avec les mêmes filtres que chercher_lots."""
        filtres, p = self._filtres_lots(gouvernorat, zone_id, surface_min, surface_max, prix_max_m2)
        return self._q("SELECT COUNT(*) AS n" + filtres, *p)[0]["n"]

    def fiche_zone(self, zone_id):
        z = self._q("SELECT * FROM v_pub_zones WHERE zone_id = %s", str(zone_id))
        if not z:
            return None
        z = z[0]
        z["distances"] = self._q("SELECT type, nom, km, source FROM v_pub_zone_distances WHERE zone_id=%s ORDER BY km",
                                 str(zone_id))
        z["equipements"] = self._q("SELECT type, valeur, unite, source FROM v_pub_zone_equipements WHERE zone_id=%s",
                                   str(zone_id))
        z["services_proches"] = self._q("SELECT categorie, nom, distance_km, source FROM v_pub_services_proches "
                                        "WHERE zone_id=%s ORDER BY distance_km", str(zone_id))
        z["cahiers_des_charges"] = self._q("SELECT annee, lien_pdf, remarque FROM v_pub_cahiers WHERE zone_id=%s",
                                           str(zone_id))
        z["plans_de_lotissement"] = self._q("SELECT nom, lien FROM v_pub_plans WHERE zone_id=%s", str(zone_id))
        return z

    def zones_proches(self, type_commodite, km_max):
        return self._q("SELECT z.zone_id, z.nom_fr, z.gouvernorat_fr, d.nom, d.km FROM v_pub_zone_distances d "
                       "JOIN v_pub_zones z USING (zone_id) WHERE d.type=%s AND d.km <= %s ORDER BY d.km",
                       type_commodite, km_max)

    def regime_gouvernorat(self, gouvernorat):
        """'developpement_regional', 'littoral' ou None si les zones (avec lots disponibles) sont mélangées."""
        r = self._q("SELECT DISTINCT z.zone_developpement_regional AS r FROM v_pub_zones z WHERE z.gouvernorat_fr LIKE %s "
                    "AND z.lots_disponibles > 0", f"%{gouvernorat}%")
        vals = {x["r"] for x in r}
        return {frozenset({1}): "developpement_regional", frozenset({0}): "littoral"}.get(frozenset(vals))
