"""Rafraîchit la copie des tables de l'AFI (base de Dalila) depuis la carte publique actuelle de l'AFI.

python -m dalila.connaissances.rafraichir_copie_afi              montre seulement les différences (rien n'est écrit)
python -m dalila.connaissances.rafraichir_copie_afi --appliquer  écrit les différences dans la copie

Pourquoi : Dalila a sa propre base MariaDB 11.8, avec une COPIE des tables de l'AFI (afi.sql) ; l'AFI ne fournit pas
de nouvel export, mais sa carte publique (carte.afi.nat.tn) lit sa base en direct. Ce script remet la copie à jour.
Les vues v_pub_* suivent aussitôt ; une correction dont la valeur AFI a changé devient « périmée » d'elle-même.

Ce qui est mis à jour (champs publics seulement ; jamais les acquéreurs, contrats ni dossiers) :
  - zones : liste des zones visibles (/zones-marqueurs), noms, prix, surfaces, gouvernorat, régime, GPS ;
  - zone_commodites : nom et valeur des distances et équipements ;
  - lots : étape, surface, numéro, nature, état ; lots nouveaux ajoutés (avec leur contour dans lots_kml).
Ce que la carte ne publie pas reste comme dans afi.sql : base de connaissances (chatbot_connaissances), services
proches, documents, lots non cessibles. Un lot de la copie absent de la carte n'est pas supprimé : il est signalé.

Limite : la carte est protégée contre les robots. Le 2026-11-27, après environ 200 requêtes dans la journée, elle a
répondu par un CAPTCHA ; le script s'arrête alors sans rien écrire. À lancer rarement (une fois par semaine au plus),
une requête par seconde ; pour un rafraîchissement régulier, demander à l'AFI un accès autorisé ou un export.
"""
import argparse, collections, json, re, time, urllib.error, urllib.request
from dalila.config import db

BASE = "https://carte.afi.nat.tn"
ZONE = {"ZONE_NAME_FR": "zone_libelle_francais", "ZONE_NAME_AR": "zone_libelle_arabe", "ZONE_GVT": "gouv_id",
        "ZONE_DEVREG": "zone_devReg", "ZONE_LAT": "zone_lat", "ZONE_LONG": "zone_long", "ZONE_PRIX": "prixunitaire",
        "ZONE_SUP_TOT": "zone_sup_total", "ZONE_SUP_AM": "zone_sup_amenager"}
LOT = {"LOT_NUM": "LOT_NUM", "LOT_SUP_LOTIS": "LOT_SUP_LOTIS", "LOT_ETAPE": "LOT_ETAPE", "LOT_NATURE": "LOT_NATURE",
       "LOT_ETAT": "LOT_ETAT"}


def lire(chemin):
    req = urllib.request.Request(BASE + chemin, headers={"User-Agent": "dalila-data-check/1.0",
                                                         "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        corps = r.read().decode("utf-8", errors="replace")
    if "captcha" in corps[:2000].lower():
        raise SystemExit("La carte de l'AFI demande un CAPTCHA (protection contre les robots) : arrêt, rien n'est écrit. "
                         "Ne pas contourner : relancer plus tard, ou demander à l'AFI un accès autorisé.")
    return json.loads(corps)


def pareil(a, b):
    if a is None or b is None:
        return (a in (None, "", 0)) and (b in (None, "", 0))
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliquer", action="store_true", help="écrire les différences dans la copie")
    a = ap.parse_args()
    con = db("root")
    cur = con.cursor()
    q = lambda sql, *p: (cur.execute(sql, p), cur.fetchall())[1]
    ecrire = []  # (requête, paramètres, description)
    stat = collections.Counter()

    # ---- zones visibles
    visibles = {str(z["id"]): z for z in lire("/zones-marqueurs")}
    copie = {str(r["code_zone"]): r for r in q("SELECT * FROM zones")}
    for zid, r in copie.items():
        vis = 1 if zid in visibles else 0
        if (r["zone_show"] == 1) != bool(vis):
            ecrire.append(("UPDATE zones SET zone_show=%s WHERE code_zone=%s", (vis, zid), f"zone {zid} visible -> {vis}"))
    for zid in visibles.keys() - copie.keys():
        stat["zone nouvelle (non ajoutée : manque dans afi.sql)"] += 1
        print("ATTENTION zone nouvelle sur la carte, absente de la copie :", zid, visibles[zid].get("ZONE_NAME_FR"))

    lots = {r["LOT_ID"]: r for r in q("SELECT LOT_ID, TRIM(ZONE_ID) z, " + ", ".join(LOT.values()) + " FROM lots")}
    vus = set()
    for zid in sorted(visibles.keys() & copie.keys()):
        try:
            d = lire(f"/zone/{zid}")
        except urllib.error.HTTPError as e:
            print(f"ATTENTION zone {zid} ({copie[zid]['zone_libelle_francais']}) : la carte répond {e.code}, zone non mise à jour")
            stat[f"zone illisible sur la carte (HTTP {e.code})"] += 1
            vus.update(i for i, b in lots.items() if b["z"] == zid)  # ses lots ne sont pas « absents de la carte »
            continue
        finally:
            time.sleep(1)
        z, r = d["zone"], copie[zid]
        for k, col in ZONE.items():
            if not pareil(z.get(k), r[col]):
                ecrire.append((f"UPDATE zones SET {col}=%s WHERE code_zone=%s", (z.get(k), zid),
                               f"zone {zid} {col} : {r[col]} -> {z.get(k)}"))
        com = {c["com_id"]: c for c in q("SELECT id, com_id, zc_libelle_francais, value FROM zone_commodites "
                                         "WHERE code_zone=%s", zid)}
        for m in d.get("commodites") or []:
            c = com.get(m["id"])
            km = re.match(r"\s*([\d.]+)", str(m.get("VALUE") or ""))
            if c is None:
                stat["commodité absente de la copie (non ajoutée)"] += 1
            elif not pareil(c["value"], m.get("VALUE")) or not pareil(c["zc_libelle_francais"], m.get("NOM_FR")):
                ecrire.append(("UPDATE zone_commodites SET value=%s, zc_libelle_francais=%s, zc_distance=%s WHERE id=%s",
                               (m.get("VALUE"), m.get("NOM_FR"), float(km.group(1)) if km else None, c["id"]),
                               f"commodité {zid}/{m['id']} : {c['value']!r} -> {m.get('VALUE')!r}"))
        for l in d.get("lots") or []:
            vus.add(l["id"])
            b = lots.get(l["id"])
            if b is None:
                ecrire.append(("INSERT INTO lots (LOT_ID, ZONE_ID, " + ", ".join(LOT.values()) + ") VALUES (%s,%s,%s,%s,%s,%s,%s)",
                               (l["id"], zid, *(l.get(k) for k in LOT)), f"lot nouveau {l['id']} ({zid} n° {l.get('LOT_NUM')})"))
                if l.get("LOT_COORDINATES"):
                    ecrire.append(("INSERT INTO lots_kml (ZONE_ID, LOT_NUM, LOT_COORDINATES) VALUES (%s,%s,%s)",
                                   (zid, l.get("LOT_NUM"), l["LOT_COORDINATES"]), f"contour du lot {l['id']}"))
                continue
            for k, col in LOT.items():
                if not pareil(l.get(k), b[col]):
                    ecrire.append((f"UPDATE lots SET {col}=%s WHERE LOT_ID=%s", (l.get(k), l["id"]),
                                   f"lot {l['id']} {col} : {b[col]} -> {l.get(k)}"))
    absents = [i for i, b in lots.items() if b["z"] in visibles and i not in vus and b["LOT_NATURE"] == 1
               and b["LOT_ETAPE"] == 1]
    print(f"{len(ecrire)} changements ; lots cessibles disponibles dans la copie mais absents de la carte : {absents}")
    for _, _, txt in ecrire:
        print("  ", txt)
    for k, v in stat.items():
        print("  ", k, ":", v)
    if a.appliquer and ecrire:
        for sql, p, _ in ecrire:
            cur.execute(sql, p)
        print("copie mise à jour. Pour les fiches de zone et le graphe : python -m dalila.connaissances.charger puis "
              "python -m dalila.connaissances.construire_abox")
    elif ecrire:
        print("(rien n'est écrit : relancer avec --appliquer)")


if __name__ == "__main__":
    main()
