"""Prépare, une fois, les données de Dalila à partir de l'archive de la fusion (dossier « dalila_fusion » du Drive).

python -m dalila.connaissances.preparer_corpus --fusion <chemin>/dalila_fusion

On ne garde que ce que l'AFI n'a pas dans sa base, nettoyé ; tout le reste est lu en direct dans la base AFI :
  donnees/corpus/passages.jsonl     textes à citer (cahiers des charges, sites officiels, guides, lois, rapports)
  donnees/corpus/pages_web.jsonl    pages web brutes (le graphe y lit les avantages TIA mot pour mot)
  db/reference/gouvernorats.csv     noms des 24 gouvernorats (fr, ar)
  db/reference/cahiers.csv          cahiers des charges : zone, année, lien du PDF officiel, remarque
  db/corrections/ancienne_carte.json  valeurs de l'ancienne carte de l'AFI (preuve pour extraire_corrections)

Nettoyage des passages :
  - retirés : copies de tables AFI (réponses de chatbot_connaissances : relues en direct au chargement), fiches de
    zone de la fusion (chiffres figés ; réécrites au chargement), doublons exacts ;
  - date de lecture de la page reprise dans `date_source` ;
  - OCR illisible (textes surtout en caractères latins ; la note n'est pas fiable pour l'arabe) : passage OCR dont moins de 60 % des mots se retrouvent dans au moins 3 autres sources -> « secondaire »
    (gardé, pas cherché) ; cahier entier dont la médiane est sous 60 % -> tous ses passages « secondaire ».
"""
import argparse, collections, csv, json, pathlib, re, statistics
from dalila.config import DONNEES, RACINE

SEUIL = 0.6
GARDER = ["id", "type", "titre", "texte", "source_url", "date_source", "langue", "zone_id", "page", "article",
          "texte_ocr", "pertinence", "raison_secondaire", "contient_chiffre"]


def arabe(t):
    """Texte surtout en arabe : la note de lisibilité n'y est pas fiable (mots moins répétés d'une source à l'autre)."""
    a = sum("؀" <= c <= "ۿ" for c in t)
    return a > 0.3 * max(1, sum(c.isalpha() for c in t))


def mots(t):
    return re.findall(r"[A-Za-zÀ-ÿ؀-ۿ]{3,}", t.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fusion", required=True, help="dossier dalila_fusion décompressé (archive de la fusion)")
    F = pathlib.Path(ap.parse_args().fusion)
    lire = lambda p: json.load(open(F / p, encoding="utf-8"))
    sortie = DONNEES / "corpus"
    sortie.mkdir(parents=True, exist_ok=True)
    ref = RACINE / "db" / "reference"
    ref.mkdir(parents=True, exist_ok=True)

    # ---- passages
    P = [json.loads(l) for l in open(F / "6_pret_pour_le_llm/passages.jsonl", encoding="utf-8")]
    retire = collections.Counter()
    vus, garde = set(), []
    for p in P:
        if p["type"] in ("reponse_validee_afi", "fiche_zone"):
            retire[p["type"]] += 1
            continue
        cle = re.sub(r"\s+", " ", p["texte"]).strip()
        if cle in vus or p.get("doublon_de"):
            retire["doublon"] += 1
            continue
        vus.add(cle)
        p["date_source"] = p.get("date_source") or p.get("lu_le")
        garde.append(p)
    source = lambda p: p.get("source_url") or p["id"]
    docs = collections.defaultdict(set)
    for p in garde:
        for w in set(mots(p["texte"])):
            docs[w].add(source(p))
    vocab = {w for w, s in docs.items() if len(s) >= 3}
    note = lambda t: (lambda w: sum(x in vocab for x in w) / len(w) if w else 0.0)(mots(t))
    par_doc = collections.defaultdict(list)
    for p in garde:
        p["_note"] = note(p["texte"])
        p["_lisible"] = bool(p.get("texte_ocr")) and not arabe(p["texte"])  # note utilisable
        if p["_lisible"]:
            par_doc[source(p)].append(p["_note"])
    illisibles = {d for d, v in par_doc.items() if statistics.median(v) < SEUIL}
    marques = collections.Counter()
    for p in garde:
        if p.get("pertinence") == "secondaire":
            continue
        if p["_lisible"] and source(p) in illisibles:
            p["pertinence"], p["raison_secondaire"] = "secondaire", "document OCR illisible dans son ensemble"
            marques["document illisible"] += 1
        elif p["_lisible"] and p["_note"] < SEUIL:
            p["pertinence"], p["raison_secondaire"] = "secondaire", f"OCR illisible (lisibilité {p['_note']:.0%})"
            marques["passage illisible"] += 1
    with open(sortie / "passages.jsonl", "w", encoding="utf-8") as fh:
        for p in garde:
            fh.write(json.dumps({k: p.get(k) for k in GARDER}, ensure_ascii=False) + "\n")
    (sortie / "pages_web.jsonl").write_bytes((F / "4_sites_officiels/pages_web.jsonl").read_bytes())

    # ---- références
    with open(ref / "gouvernorats.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "nom_fr", "nom_ar"])
        w.writerows(sorted((g["code"], g["nom_fr"], g["nom_ar"]) for g in lire("1_zones_et_lots/gouvernorats.json")))
    with open(F / "2_cahiers_des_charges/index.csv", encoding="utf-8-sig") as fe, \
            open(ref / "cahiers.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["zone_id", "zone", "annee", "lecture", "lien_pdf", "remarque"])
        w.writeheader()
        for r in csv.DictReader(fe):
            w.writerow({k: r[k] for k in w.fieldnames})

    # ---- preuve : ancienne carte (valeurs que la fusion en a reprises)
    zones = {z["zone_id"]: {"nom_fr": z["nom_fr"], "nom_ar": z["nom_ar"], "surface_totale_m2": z["surface_totale_m2"],
                            "surface_amenagee_m2": z["surface_amenagee_m2"], "prix_m2_dt": z["prix_m2_dt"],
                            "distances": {t: {"nom": v.get("nom"), "km": v.get("km"), "source": v.get("source")}
                                          for t, v in (z.get("distances") or {}).items() if v}}
             for z in lire("1_zones_et_lots/zones.json")}
    lots = {str(l["lot_id"]): {"etape": l["etape_retenue"], "surface_m2": l["surface_m2"]}
            for l in lire("1_zones_et_lots/lots.json")}
    (RACINE / "db" / "corrections" / "ancienne_carte.json").write_text(json.dumps(
        {"source": "ancienne carte publique afi.e-industrie.gov.tn, relevée le 2026-11-25 (fusion)",
         "zones": zones, "lots": lots}, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"passages gardés : {len(garde)} ; retirés : {dict(retire)} ; marqués secondaires : {dict(marques)} ; "
          f"documents illisibles : {sorted(illisibles)}")


if __name__ == "__main__":
    main()
