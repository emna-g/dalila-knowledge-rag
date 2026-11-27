"""Liste FERMÉE des sources à relire : dalila/sources/config_sources.csv (BF14, BNF14).

python -m dalila.sources.inventaire              montre les URL utilisées par Dalila et absentes de la liste
python -m dalila.sources.inventaire --ecrire     les ajoute à la liste ; une URL qui n'est plus citée passe à actif = 0
                                                 (avec la date en remarque) ; aucune autre ligne n'est modifiée

Les URL sont relevées là où Dalila les cite : fichiers db/reference/*.csv et, s'il est présent, le corpus
(donnees/corpus/passages.jsonl). La liste se relit et se corrige à la main : une ligne avec actif = 0 n'est pas lue.
Sites jamais relus automatiquement (actif = 0 d'office) : voir HORS_LECTURE.
"""
import argparse, csv, datetime, json, re, sys, urllib.parse
from dalila.config import DONNEES, RACINE

CONFIG = RACINE / "dalila" / "sources" / "config_sources.csv"
COLONNES = ["url", "organisme", "type", "delai_jours", "actif", "utilise_par", "remarque"]
REFERENCE = RACINE / "db" / "reference"
DELAI_JOURS = 7  # « au moins chaque semaine » (cahier des charges, BF14)

ORGANISMES = {"afi.nat.tn": "AFI", "investintunisia.tn": "FIPA", "tunisieindustrie.nat.tn": "APII",
              "tia.gov.tn": "TIA", "sicad.gov.tn": "SICAD", "apia.com.tn": "APIA", "ins.tn": "INS"}
HORS_LECTURE = {  # site -> raison (docs/decisions.md, « Fraîcheur des données » ; docs/limites.md)
    "carte.afi.nat.tn": "carte de l'AFI protégée par CAPTCHA : relue seulement par rafraichir_copie_afi, à la main",
    "afi.e-industrie.gov.tn": "ancienne carte de l'AFI, remplacée par carte.afi.nat.tn",
    "ins.tn": "INS : cité seulement (cahier des charges, site protégé par CAPTCHA)",
    "sicad.gov.tn": "robots.txt du site interdit la lecture automatique (vérifié le 2026-11-27) : extraits de la base "
                    "AFI seulement (docs/limites.md)",
    "unctad.org": "robots.txt du site interdit la lecture automatique (vérifié le 2026-11-27)",
}
URL = re.compile(r"https?://[^\s\"<>]+")


def organisme(url):
    s = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    return next((o for d, o in ORGANISMES.items() if s == d or s.endswith("." + d)), s)


def hors_lecture(url):
    s = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    return next((r for d, r in HORS_LECTURE.items() if s == d or s.endswith("." + d)), None)


def type_de(url):
    return "pdf" if urllib.parse.urlsplit(url).path.lower().endswith(".pdf") else "page"


def urls_reference(dossier=REFERENCE):
    """{url: {fichiers qui la citent}}. cahiers.csv : colonne lien_pdf (le nom de fichier peut contenir des espaces) ;
    les autres fichiers : URL écrites dans le texte des colonnes (source…)."""
    trouvees = {}
    for f in sorted(dossier.glob("*.csv")):
        for ligne in csv.DictReader(open(f, encoding="utf-8-sig")):
            if f.name == "cahiers.csv":
                urls = [ligne["lien_pdf"].strip()] if (ligne.get("lien_pdf") or "").strip() else []
            else:
                urls = [u.rstrip(".,;)") for v in ligne.values() if v for u in URL.findall(v)]
            for u in urls:
                trouvees.setdefault(u, set()).add(f"db/reference/{f.name}")
    return trouvees


def urls_corpus(fichier=None):
    """{url: {"corpus"}} depuis passages.jsonl (absent si le corpus n'est pas sur cette machine)."""
    fichier = fichier or DONNEES / "corpus" / "passages.jsonl"
    trouvees = {}
    if fichier.exists():
        for l in open(fichier, encoding="utf-8"):
            u = (json.loads(l).get("source_url") or "").strip()
            if u.startswith("http"):
                trouvees.setdefault(u, set()).add("corpus")
    return trouvees


def lire_config(chemin=CONFIG):
    if not chemin.exists():
        return []
    return list(csv.DictReader(open(chemin, encoding="utf-8-sig")))


def sources_actives(chemin=CONFIG):
    return [r for r in lire_config(chemin) if r["actif"].strip() == "1"]


def nouvelles_lignes(existantes, trouvees):
    connues = {r["url"] for r in existantes}
    lignes = []
    for u in sorted(trouvees.keys() - connues):
        raison = hors_lecture(u)
        lignes.append({"url": u, "organisme": organisme(u), "type": type_de(u), "delai_jours": DELAI_JOURS,
                       "actif": 0 if raison else 1, "utilise_par": ";".join(sorted(trouvees[u])),
                       "remarque": raison or ""})
    return lignes


def plus_citees(existantes, trouvees, corpus_present):
    """Lignes actives dont l'URL n'est plus citée (lien corrigé, source retirée). Une URL citée par le corpus n'est
    jugée que si le corpus est sur cette machine."""
    return [r for r in existantes if r["actif"].strip() == "1" and r["url"] not in trouvees
            and (corpus_present or "corpus" not in r.get("utilise_par", ""))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ecrire", action="store_true", help="ajouter les URL manquantes à config_sources.csv")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console Windows
    trouvees = urls_reference()
    for u, f in urls_corpus().items():
        trouvees.setdefault(u, set()).update(f)
    existantes = lire_config()
    nouvelles = nouvelles_lignes(existantes, trouvees)
    retirees = plus_citees(existantes, trouvees, (DONNEES / "corpus" / "passages.jsonl").exists())
    print(f"{len(trouvees)} URL citées par Dalila ; {len(existantes)} dans la liste ; {len(nouvelles)} à ajouter ; "
          f"{len(retirees)} plus citées")
    for r in nouvelles:
        print(f"  + [{r['organisme']}] {r['url']}" + (f"   (inactive : {r['remarque']})" if r["remarque"] else ""))
    for r in retirees:
        print(f"  - [{r['organisme']}] {r['url']}   (plus citée : passe à actif = 0)")
    if a.ecrire and (nouvelles or retirees):
        for r in retirees:
            r["actif"] = 0
            r["remarque"] = (r["remarque"] + " ; " if r["remarque"] else "") +                 f"plus citée par Dalila depuis le {datetime.date.today()} (lien corrigé ou source retirée)"
        with open(CONFIG, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLONNES)
            w.writeheader()
            w.writerows(existantes + nouvelles)
        print("écrit :", CONFIG.relative_to(RACINE))


if __name__ == "__main__":
    main()
