"""Compare trois sources et écrit les corrections que Dalila applique sur la base AFI lue en direct.

python -m dalila.connaissances.lire_carte_afi           (1) relevé de la carte publique actuelle de l'AFI
python -m dalila.connaissances.extraire_corrections     (2) ce script (afi.sql chargé tel quel dans la base)

Sources :
  - base      : tables de l'AFI (afi.sql, lues en direct par les vues v_pub_*) ;
  - actuelle  : carte publique actuelle de l'AFI (carte.afi.nat.tn), db/corrections/carte_afi_actuelle.json ;
  - ancienne  : ancienne carte (afi.e-industrie.gov.tn), relevée le 2026-11-25 pour la fusion des données
                (valeurs gardées dans db/corrections/ancienne_carte.json par dalila.connaissances.preparer_corpus).

Constat (relevé du 2026-11-26) : la carte actuelle donne exactement les valeurs de la base (zones, distances,
équipements, lots), sauf quelques étapes de lots changées depuis l'export. C'est l'ancienne carte qui diffère.
Règle : les données actuelles de l'AFI l'emportent.
  1. carte actuelle ≠ base  -> correction appliquée (l'AFI a changé la valeur depuis l'export) ;
  2. ancienne carte ≠ base  -> gardée pour mémoire, non appliquée (sauf orthographe des noms de distances) ;
     ses noms de zones deviennent des noms alternatifs (reconnus dans les questions, non affichés) ;
  3. contrôles Dalila       -> prix impossible masqué ; distances d'une zone sans distances reprises de la zone
     voisine (< 1 km) ; lots disponibles dans la base mais pas sur la carte actuelle : « à confirmer ».

Écrit dans db/corrections/ : dalila_corrections.csv, lots_a_confirmer.csv, alias_zones.csv, DESACCORDS.md.
Pour changer une décision : colonne `appliquee` du CSV, puis python -m dalila.connaissances.charger.
"""
import csv, difflib, json, math, re
from dalila.config import RACINE, db

SORTIE = RACINE / "db" / "corrections"
ANCIENNE = "ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion)"
CONTROLE = "contrôle Dalila (données AFI)"
COLONNES = ["table_afi", "cle", "champ", "valeur_afi", "valeur_corrigee", "appliquee", "source", "raison"]
DISTANCES = {1: "aeroport", 2: "port", 3: "gare", 4: "autoroute", 5: "gazoduc"}
ZONES = [("zone_libelle_francais", "nom_fr", "ZONE_NAME_FR", "texte"), ("zone_libelle_arabe", "nom_ar", "ZONE_NAME_AR", "texte"),
         ("zone_sup_total", "surface_totale_m2", "ZONE_SUP_TOT", "nombre"),
         ("zone_sup_amenager", "surface_amenagee_m2", "ZONE_SUP_AM", "nombre"),
         ("prixunitaire", "prix_m2_dt", "ZONE_PRIX", "nombre")]
# Textes de la base de connaissances AFI (chatbot_connaissances) : (id, extrait faux, extrait juste, preuve)
TEXTE_KB = [
    (3, "+216 260 124 71", "+216 71 124 260", "page contact du site de l'AFI (afi.nat.tn/fr/contact) : bureau des "
                                              "relations avec le citoyen (216+) 71124260 ; même numéro que la réponse 26"),
    (3, "+216 242 124 71", "+216 71 124 242", "page contact du site de l'AFI (afi.nat.tn/fr/contact) : direction "
                                              "des affaires commerciales (216+) 71124242"),
]
PRIX_MAX = 500  # DT/m² : au-delà, valeur impossible (le plus cher des prix AFI publiés est 120)

# Ce que nos données montrent sur les valeurs de l'ancienne carte (GPS des zones ; une route mesure environ 1,2 à
# 1,4 fois la ligne droite). Ajouté à la raison, pour mémoire.
PREUVE = {
    ("930607", "aeroport"): "l'aéroport d'Enfidha est à environ 3 km à vol d'oiseau : 68 km impossible",
    ("930920", "aeroport"): "aéroport d'Enfidha à environ 23 km à vol d'oiseau : 90 km impossible",
    ("931500", "gare"): "la zone est à 11 km de la zone de Jendouba, dont la gare est à 5 km : 149 km impossible",
    ("931501", "gare"): "zone dans Jendouba : 161 km impossible",
    ("9315043", "gare"): "Tabarka 2 est à 51 km de la zone de Jendouba (gare à 5 km) : 188 km impossible",
    ("931500", "aeroport"): "Tunis-Carthage est à 125 km à vol d'oiseau : 79 km ne peut être que Tabarka",
    ("931501", "aeroport"): "Tunis-Carthage est à 130 km à vol d'oiseau : 85 km ne peut être que Tabarka",
    ("9315043", "aeroport"): "Tunis-Carthage est à 125 km à vol d'oiseau : 17 km ne peut être que Tabarka",
    ("932114", "gare"): "Gabès est à environ 168 km à vol d'oiseau : 3 km ne peut être que Tozeur",
    ("931100", "port"): "Gabès est à 111 km à vol d'oiseau : 100 km par la route impossible",
    ("931103", "port"): "Gabès est à 67 km à vol d'oiseau : 65 km par la route impossible",
    ("931803", "gare"): "El Krib est à 18 km de Gaafour, dont la gare est à 1 km : la gare de Gaafour à 16 km est cohérente",
    ("930900", "zone_sup_total"): "le site de l'AFI (page « المناطق المهيئة ») donne 31 ha, et les lots couvrent déjà "
                                  "plus de 150 000 m²",
    ("931804", "prixunitaire"): "118 DT/m² serait de loin le prix le plus élevé des zones de développement régional",
}


def txt(v):
    """Valeur écrite comme CAST(... AS CHAR) côté base : 68.0 -> '68'."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def meme(a, b, genre):
    if genre == "texte":
        return str(a or "").strip() == str(b or "").strip()
    try:
        return float(a or 0) == float(b or 0)
    except (TypeError, ValueError):
        return False


def orthographe(a, b):
    """Même nom écrit autrement (Ennfidha / Enfidha, Jerba / Djerba, GP1 / GP 1)."""
    n = lambda x: re.sub(r"\s+", "", (x or "").lower())
    return difflib.SequenceMatcher(None, n(a), n(b)).ratio() >= 0.8


def km_de(valeur):
    m = re.match(r"\s*([\d.]+)", str(valeur or ""))
    return float(m.group(1)) if m else None


def hav(a, b, x, y):
    p1, p2 = math.radians(a), math.radians(x)
    return 2 * 6371 * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 +
                                          math.cos(p1) * math.cos(p2) * math.sin(math.radians(y - b) / 2) ** 2))


def main():
    con = db("root")
    q = lambda sql, *p: (lambda cur: (cur.execute(sql, p), cur.fetchall())[1])(con.cursor())
    carte = json.load(open(SORTIE / "carte_afi_actuelle.json", encoding="utf-8"))
    ACTUELLE = f"carte publique actuelle de l'AFI carte.afi.nat.tn (relevée le {carte['lu_le']})"
    NZ = carte["zones"]
    vieille = json.load(open(SORTIE / "ancienne_carte.json", encoding="utf-8"))
    fz = vieille["zones"]
    fl = {int(k): {"etape_retenue": v["etape"], "surface_m2": v["surface_m2"]} for k, v in vieille["lots"].items()}
    az = {r["code_zone"]: r for r in q(
        "SELECT CAST(code_zone AS CHAR) code_zone, " + ", ".join(f"CAST({c} AS CHAR) {c}" for c, *_ in ZONES) +
        ", CAST(zone_lat AS DOUBLE) lat, CAST(zone_long AS DOUBLE) lng, zone_show FROM zones")}
    al = {r["LOT_ID"]: r for r in q("SELECT LOT_ID, TRIM(ZONE_ID) zone_id, TRIM(LOT_NUM) lot_num, LOT_NATURE, "
                                    "CAST(LOT_SUP_LOTIS AS CHAR) LOT_SUP_LOTIS, CAST(LOT_ETAPE AS CHAR) LOT_ETAPE FROM lots")}
    ac = {(r["code_zone"], r["com_id"]): r for r in q(
        "SELECT CAST(code_zone AS CHAR) code_zone, com_id, zc_libelle_francais, CAST(zc_distance AS CHAR) zc_distance, "
        "value FROM zone_commodites WHERE code_zone <> 0")}
    lignes, alias, accord = {}, [], {"zones": [0, 0], "commodites": [0, 0], "lots": [0, 0]}

    def ajoute(table, cle, champ, afi, corr, source, raison, appliquee=1):
        if (table, cle, champ) not in lignes:  # la première source qui corrige un champ l'emporte (ordre : 1, 3, 2)
            lignes[(table, cle, champ)] = {"table_afi": table, "cle": cle, "champ": champ, "valeur_afi": afi,
                                           "valeur_corrigee": txt(corr), "appliquee": appliquee, "source": source,
                                           "raison": raison}

    # ---- 1. carte actuelle ≠ base : l'AFI a changé la valeur depuis l'export
    nl = {}
    for zid, n in NZ.items():
        a = az[zid]
        for c, _, nk, g in ZONES:
            accord["zones"][0] += 1
            if meme(a[c], n["zone"][nk], g):
                accord["zones"][1] += 1
            else:
                ajoute("zones", zid, c, a[c], n["zone"][nk], ACTUELLE, "valeur changée par l'AFI depuis l'export afi.sql")
        for m in n["commodites"]:
            b = ac.get((zid, m["id"]))
            accord["commodites"][0] += 1
            accord["commodites"][1] += bool(b) and str(b["value"] or "").strip() == str(m["valeur"] or "").strip() \
                and str(b["zc_libelle_francais"] or "").strip() == str(m["nom"] or "").strip()
        for l in n["lots"]:
            nl[l["id"]] = l
            b = al.get(l["id"])
            if b is None:
                continue
            accord["lots"][0] += 1
            ok = meme(b["LOT_ETAPE"], l["LOT_ETAPE"], "nombre") and meme(b["LOT_SUP_LOTIS"], l["LOT_SUP_LOTIS"], "nombre")
            accord["lots"][1] += ok
            if not meme(b["LOT_ETAPE"], l["LOT_ETAPE"], "nombre"):
                ajoute("lots", str(l["id"]), "LOT_ETAPE", b["LOT_ETAPE"], l["LOT_ETAPE"], ACTUELLE,
                       f"étape changée par l'AFI depuis l'export afi.sql (« {l['ETAPE_LIB_FR']} » sur la carte actuelle)")
            if not meme(b["LOT_SUP_LOTIS"], l["LOT_SUP_LOTIS"], "nombre"):
                ajoute("lots", str(l["id"]), "LOT_SUP_LOTIS", b["LOT_SUP_LOTIS"], l["LOT_SUP_LOTIS"], ACTUELLE,
                       "surface changée par l'AFI depuis l'export afi.sql")

    # ---- 3. contrôles Dalila
    for zid, a in az.items():
        if a["zone_show"] == 1 and float(a["prixunitaire"] or 0) > PRIX_MAX:
            ajoute("zones", zid, "prixunitaire", a["prixunitaire"], None, CONTROLE,
                   f"prix impossible ({a['prixunitaire']} DT/m², sans doute une année) : masqué, « prix non publié »")
    avec = {z for z, _ in ac if any((z, c) in ac for c in DISTANCES)}
    for zid, a in az.items():
        if a["zone_show"] != 1 or zid in avec:
            continue
        voisins = sorted((hav(a["lat"], a["lng"], b["lat"], b["lng"]), z) for z, b in az.items() if z in avec and z != zid)
        if not voisins or voisins[0][0] > 1:
            continue
        d, v = voisins[0]
        for cid, t in DISTANCES.items():
            b = ac.get((v, cid))
            if b is None or b["zc_distance"] is None or (t == "gazoduc" and str(b["zc_libelle_francais"]).strip().upper().startswith("RN")):
                continue
            src = f"base AFI, zone voisine {v} {az[v]['zone_libelle_francais']} (à {d:.1f} km)"
            vieux = (fz.get(zid, {}).get("distances") or {}).get(t) or {}
            r = ("zone sans distances dans la base : valeurs de la zone voisine" +
                 (" (l'ancienne carte donne les mêmes)" if meme(vieux.get("km"), b["zc_distance"], "nombre") else ""))
            ajoute("zone_commodites", f"{zid}:{cid}", "zc_distance", None, b["zc_distance"], src, r)
            ajoute("zone_commodites", f"{zid}:{cid}", "zc_libelle_francais", None, str(b["zc_libelle_francais"]).strip(), src, r)

    kb = {r["id"]: r["reponse"] for r in q("SELECT id, reponse FROM chatbot_connaissances")}
    for n, (i, faux, juste, preuve) in enumerate(TEXTE_KB, 1):
        if faux in kb.get(i, ""):
            ajoute("chatbot_connaissances", f"{i}:{n}", "reponse (extrait)", faux, juste, preuve,
                   "chiffres du numéro dans le désordre dans la réponse de l'AFI")

    # ---- 2. ancienne carte ≠ base : pour mémoire
    garde = "non appliquée : la carte actuelle de l'AFI donne la valeur de la base"
    for zid, f in fz.items():
        a = az[zid]
        for c, fk, _, g in ZONES:
            if not meme(a[c], f.get(fk), g):
                p = PREUVE.get((zid, c))
                ajoute("zones", zid, c, a[c], f.get(fk), ANCIENNE, garde + (f" ; {p}" if p else ""), 0)
                if fk.startswith("nom") and f.get(fk):
                    alias.append({"zone_id": zid, "alias": f[fk].strip(), "langue": "ar" if fk == "nom_ar" else "fr",
                                  "source": ANCIENNE})
    for lid, f in fl.items():
        a = al[lid]
        if not meme(a["LOT_ETAPE"], f["etape_retenue"], "nombre"):
            ajoute("lots", str(lid), "LOT_ETAPE", a["LOT_ETAPE"], f["etape_retenue"], ANCIENNE, garde, 0)
        if not meme(a["LOT_SUP_LOTIS"], f["surface_m2"], "nombre"):
            ajoute("lots", str(lid), "LOT_SUP_LOTIS", a["LOT_SUP_LOTIS"], f["surface_m2"], "fusion, sans source",
                   garde + " ; la surface de la fusion n'a pas de source", 0)
    for zid, f in fz.items():
        for cid, t in DISTANCES.items():
            v = (f.get("distances") or {}).get(t)
            a = ac.get((zid, cid))
            if not v or v.get("km") is None or a is None:
                continue
            cle, p = f"{zid}:{cid}", PREUVE.get((zid, t))
            raison = garde + (f" ; {p}" if p else "")
            if not meme(a["zc_distance"], v["km"], "nombre"):
                ajoute("zone_commodites", cle, "zc_distance", a["zc_distance"], v["km"], ANCIENNE, raison, 0)
            if not meme(a["zc_libelle_francais"], v.get("nom"), "texte"):
                ok = orthographe(a["zc_libelle_francais"], v.get("nom"))
                ajoute("zone_commodites", cle, "zc_libelle_francais", a["zc_libelle_francais"], v.get("nom"), ANCIENNE,
                       "correction d'orthographe" if ok else raison, int(ok))

    # ---- lots disponibles dans la base, mais pas sur la carte actuelle
    vis = {z for z, a in az.items() if a["zone_show"] == 1}
    confirmer = []
    for lid, a in al.items():
        if a["zone_id"] in vis and a["LOT_ETAPE"] == "1" and a["LOT_NATURE"] == 1 and float(a["LOT_SUP_LOTIS"] or 0) > 0:
            l = nl.get(lid)
            if l is None or not l["disponible"]:
                confirmer.append({"lot_id": lid, "etape_afi": 1, "source": ACTUELLE,
                                  "raison": "disponible dans la base (export afi.sql), mais " +
                                            ("absent de la carte actuelle de l'AFI" if l is None
                                             else f"« {l['ETAPE_LIB_FR']} » sur la carte actuelle")})

    lignes = sorted(lignes.values(), key=lambda l: (-int(l["appliquee"]), l["table_afi"], l["cle"], l["champ"]))
    SORTIE.mkdir(parents=True, exist_ok=True)
    for nom, rows, cols in (("dalila_corrections.csv", lignes, COLONNES),
                            ("lots_a_confirmer.csv", confirmer, ["lot_id", "etape_afi", "raison", "source"]),
                            ("alias_zones.csv", alias, ["zone_id", "alias", "langue", "source"])):
        with open(SORTIE / nom, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    ecrire_desaccords(lignes, az, confirmer, alias, accord, carte["lu_le"])
    n1 = sum(1 for l in lignes if l["appliquee"])
    print(f"{len(lignes)} corrections ({n1} appliquées, {len(lignes) - n1} pour mémoire), {len(confirmer)} lots à "
          f"confirmer, {len(alias)} noms alternatifs ; accord carte actuelle / base : "
          + ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in accord.items()))


def ecrire_desaccords(lignes, az, confirmer, alias, accord, lu_le):
    nom = lambda z: (az.get(z) or {}).get("zone_libelle_francais", "").strip()
    cel = lambda v: "—" if v is None or v == "" else str(v).strip().replace("|", "/")

    def element(l):
        if l["table_afi"] == "lots":
            return f"Lot {l['cle']}"
        if l["table_afi"] == "chatbot_connaissances":
            return f"Réponse AFI n° {l['cle'].split(':')[0]}"
        if l["table_afi"] == "zone_commodites":
            z, c = l["cle"].split(":")
            return f"Distance {z} {nom(z)} → {DISTANCES[int(c)]}"
        return f"Zone {l['cle']} {nom(l['cle'])}"

    def tableau(rows):
        out = ["| Élément | Champ | Base AFI | Autre valeur | Source de l'autre valeur | Raison |", "|---|---|---|---|---|---|"]
        out += [f"| {element(l)} | {l['champ']} | {cel(l['valeur_afi'])} | {cel(l['valeur_corrigee'])} | "
                f"{cel(l['source'])} | {cel(l['raison'])} |" for l in rows]
        return out

    oui = [l for l in lignes if l["appliquee"]]
    non = [l for l in lignes if not l["appliquee"]]
    md = ["# Désaccords entre les sources, et décisions",
          "",
          "Produit par `python -m dalila.connaissances.extraire_corrections`. Dalila lit la base AFI en direct ; chaque ligne "
          "est une correction de `dalila_corrections.csv`. Pour changer une décision : colonne `appliquee`, puis "
          "`python -m dalila.connaissances.charger`.",
          "",
          "## Les sources",
          "",
          "| Source | Ce que c'est |",
          "|---|---|",
          "| Base AFI (`afi.sql`) | Les tables de l'AFI, lues en direct par Dalila. |",
          f"| Carte actuelle de l'AFI | carte.afi.nat.tn, relevée le {lu_le} (`carte_afi_actuelle.json`, par "
          "`dalila.connaissances.lire_carte_afi`). Elle lit la base de l'AFI. |",
          "| Ancienne carte | afi.e-industrie.gov.tn, relevée le 2026-11-25 pour la fusion. |",
          "",
          "Accord entre la carte actuelle et la base : "
          + ", ".join(f"{k} {v[1]} / {v[0]}" for k, v in accord.items())
          + ". La carte actuelle donne donc les valeurs de la base ; c'est l'ancienne carte qui diffère "
          "(noms, prix, surfaces, distances). Nos propres contrôles (GPS, contours des lots, site de l'AFI) "
          "donnent tort à l'ancienne carte chaque fois qu'ils permettent de trancher.",
          "",
          "## Règles de décision",
          "",
          "1. **Les données actuelles de l'AFI l'emportent** (base, ou carte actuelle quand l'AFI a changé une valeur "
          "depuis l'export).",
          "2. **Ancienne carte :** gardée pour mémoire, non appliquée. Exceptions : orthographe des noms de distances "
          "(Ennfidha → Enfidha…). Ses noms de zones (« ENFIDHA 2 », « KASSERINE 2 »…) deviennent des **noms "
          "alternatifs** : reconnus dans les questions, mais Dalila affiche le nom de l'AFI.",
          f"3. **Prix impossible** (plus de {PRIX_MAX} DT/m²) : masqué, Dalila dit « prix non publié ». Prix à 0 : "
          "« prix non publié par l'AFI » (Gabès, Sousse I et II, Hstaftimi).",
          "4. **Réponses de la base de connaissances AFI :** relues en direct ; une erreur prouvée (numéro de "
          "téléphone mal écrit) est corrigée par extrait, tant que l'extrait faux s'y trouve encore.",
          "5. **Zone sans distances** dans la base : distances de la zone voisine à moins de 1 km (Kasserine Extention "
          "← Kasserine, à 0,4 km).",
          "6. **Lot disponible dans la base mais pas sur la carte actuelle :** gardé, avec « à confirmer auprès de "
          "l'AFI ».",
          "",
          "## Règles d'affichage (vues `v_pub_*`)",
          "",
          "- Seuls les lots **cessibles** (`LOT_NATURE` = 1) sont listés : c'est la règle de la carte de l'AFI. Les "
          "autres (équipements publics, voirie…) ne sont pas à vendre.",
          "- Équipement à **0** (électricité, eau, gaz, téléphone) : non montré ; 0 veut dire « non renseigné ».",
          "- Gazoduc nommé par une route (« RN … ») : non montré (la base et la carte actuelle donnent une route ; la "
          "valeur n'est pas fiable).",
          "- Contour de lot dont l'aire n'est pas entre 2/3 et 1,5 fois la surface du lot : non dessiné.",
          "- Distance à **0 km** : à dire « à moins d'un kilomètre ».",
          "- Surface aménagée : citée telle que l'AFI la donne, sans calcul. La surface totale de la base est celle du "
          "site de l'AFI (page « المناطق المهيئة »).",
          "- Enchères : ni la base ni la carte actuelle ne donnent de dates ou de mise à prix (champs vides).",
          "",
          f"## Corrections appliquées ({len(oui)})",
          "",
          *tableau(oui),
          "",
          f"## Lots à confirmer ({len(confirmer)})",
          "",
          "| Lot | Raison |", "|---|---|",
          *[f"| {c['lot_id']} | {c['raison']} |" for c in confirmer],
          "",
          f"## Noms alternatifs ({len(alias)})",
          "",
          "| Zone | Nom AFI (affiché) | Nom alternatif (reconnu) |", "|---|---|---|",
          *[f"| {a['zone_id']} | {nom(a['zone_id'])} | {a['alias']} |" for a in alias],
          "",
          f"## Valeurs de l'ancienne carte non retenues ({len(non)})",
          "",
          *tableau(non),
          ""]
    (SORTIE / "DESACCORDS.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
