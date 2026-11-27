"""Relève la carte publique actuelle de l'AFI (carte.afi.nat.tn) pour les zones visibles, et en garde un extrait.

python -m dalila.connaissances.lire_carte_afi        (base AFI chargée : la liste des zones vient de `zones`)

La carte lit la base de l'AFI : le relevé sert de preuve pour départager la base (export afi.sql) et l'ancienne carte
(afi.e-industrie.gov.tn) relevée pour la fusion. Résultat : db/corrections/carte_afi_actuelle.json (sans contours ni
images ; aucune donnée personnelle : la carte n'en publie pas). Une requête par seconde.
"""
import datetime, json, time, urllib.request
from dalila.config import RACINE, db

URL = "https://carte.afi.nat.tn/zone/{}"
SORTIE = RACINE / "db" / "corrections" / "carte_afi_actuelle.json"
ZONE = ["ZONE_NAME_FR", "ZONE_NAME_AR", "ZONE_PRIX", "ZONE_SUP_TOT", "ZONE_SUP_AM", "ZONE_GVT", "ZONE_DEVREG",
        "ZONE_LAT", "ZONE_LONG", "ZONE_SHOW"]
LOT = ["id", "LOT_NUM", "LOT_SUP_LOTIS", "LOT_ETAPE", "ETAPE_LIB_FR", "LOT_NATURE", "disponible",
       "ENCHERE_MISE_A_PRIX", "ENCHERE_DATE_DEBUT", "ENCHERE_LIMITE_DEPOT"]


def lire(zone_id):
    req = urllib.request.Request(URL.format(zone_id), headers={"User-Agent": "dalila-data-check/1.0",
                                                              "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        corps = r.read().decode("utf-8", errors="replace")
    if "captcha" in corps[:2000].lower():
        raise SystemExit("La carte de l'AFI demande un CAPTCHA (protection contre les robots) : arrêt. Ne pas contourner.")
    return json.loads(corps)


def main():
    with db("ro") as con:
        with con.cursor() as cur:
            cur.execute("SELECT zone_id AS z FROM v_pub_zones ORDER BY zone_id")
            ids = [r["z"] for r in cur.fetchall()]
    out = {"source": "carte publique actuelle de l'AFI, carte.afi.nat.tn",
           "lu_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), "zones": {}}
    for i in ids:
        d = lire(i)
        out["zones"][i] = {"zone": {k: d["zone"].get(k) for k in ZONE},
                           "commodites": [{"id": m["id"], "nom": m.get("NOM_FR"), "valeur": m.get("VALUE")}
                                          for m in d.get("commodites") or []],
                           "lots": [{k: l.get(k) for k in LOT} for l in d.get("lots") or []]}
        time.sleep(1)
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(out['zones'])} zones relevées le {out['lu_le']} -> {SORTIE}")


if __name__ == "__main__":
    main()
