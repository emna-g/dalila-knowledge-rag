"""Les chiffres de Dalila, lus dans la base SQLite (jamais inventés par le LLM).

    from chiffres import Chiffres
    c = Chiffres()
    c.chercher_lots(gouvernorat="Sfax", surface_min=1000, surface_max=5000)
    c.zone("930900")
    c.zones_proches("port", km_max=10)

Chaque résultat garde sa source. Les lots « a_confirmer » doivent être annoncés comme à confirmer.
"""
import sqlite3, pathlib

ICI = pathlib.Path(__file__).resolve().parent


class Chiffres:
    def __init__(self, base=ICI / "base" / "dalila.sqlite"):
        self.db = sqlite3.connect(str(base))
        self.db.row_factory = sqlite3.Row

    def _q(self, sql, *p):
        return [dict(r) for r in self.db.execute(sql, p)]

    def chercher_lots(self, gouvernorat=None, zone_id=None, surface_min=None, surface_max=None, prix_max_m2=None,
                      limite=20):
        """Lots disponibles, du moins cher au plus cher (prix au m² de la zone)."""
        sql = ("SELECT l.*, z.gouvernorat_fr FROM v_pub_lots_disponibles l JOIN v_pub_zones z USING(zone_id) WHERE 1=1")
        p = []
        if gouvernorat:
            sql += " AND (z.gouvernorat_fr LIKE ? OR z.gouvernorat_ar LIKE ?)"; p += [f"%{gouvernorat}%"] * 2
        if zone_id:
            sql += " AND l.zone_id = ?"; p.append(str(zone_id))
        if surface_min:
            sql += " AND l.surface_m2 >= ?"; p.append(surface_min)
        if surface_max:
            sql += " AND l.surface_m2 <= ?"; p.append(surface_max)
        if prix_max_m2:
            sql += " AND l.prix_m2_dt IS NOT NULL AND l.prix_m2_dt <= ?"; p.append(prix_max_m2)
        sql += " ORDER BY l.prix_m2_dt IS NULL, l.prix_m2_dt, l.surface_m2 LIMIT ?"
        p.append(limite)
        return self._q(sql, *p)

    def zone(self, zone_id):
        z = self._q("SELECT * FROM v_pub_zones WHERE zone_id = ?", str(zone_id))
        if not z:
            return None
        z = z[0]
        z["distances"] = self._q("SELECT type, nom, km, source FROM zone_distances WHERE zone_id = ?", str(zone_id))
        z["equipements"] = self._q("SELECT type, valeur, unite FROM zone_equipements WHERE zone_id = ?", str(zone_id))
        z["cahiers_des_charges"] = self._q("SELECT annee, lien_pdf, remarque FROM cahiers_des_charges WHERE zone_id = ?",
                                           str(zone_id))
        return z

    def zones_proches(self, type_commodite, km_max):
        """type_commodite : aeroport, port, gare, autoroute, gazoduc."""
        return self._q("SELECT z.zone_id, z.nom_fr, z.gouvernorat_fr, d.nom, d.km FROM zone_distances d "
                       "JOIN v_pub_zones z USING(zone_id) WHERE d.type = ? AND d.km <= ? ORDER BY d.km",
                       type_commodite, km_max)


if __name__ == "__main__":
    c = Chiffres()
    for l in c.chercher_lots(gouvernorat="Sfax", limite=5):
        print(l)
    print(c.zones_proches("port", 10))
