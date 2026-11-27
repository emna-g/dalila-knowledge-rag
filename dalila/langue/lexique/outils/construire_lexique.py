# -*- coding: utf-8 -*-
"""
Construit le lexique tunisien de Dalila a partir de vraies donnees.

Usage :
    python -m dalila.langue.lexique.outils.construire_lexique [--sortie ..]   (depuis la racine du projet ; base MariaDB chargée ;
    corpus TArC, TUNIZI et TSAC dans dalila/langue/lexique/sources/, à prendre dans lexique_tunisien.zip du Drive, hors git)

Etapes :
 1. Lit les propositions (candidats.py).
 2. Cherche chaque forme dans 5 sources reelles et compte les occurrences :
      - conv_afi   : les questions des visiteurs du chatbot de l'AFI (table chatbot_logs de la base AFI)
      - cdc_afi    : le cahier des charges officiel du hackathon (exemples cites, avec la page)
      - ar_afi     : les 900 passages en arabe de l'AFI (pour l'arabe standard)
      - tarc       : corpus TArC (arabizi tunisien transcrit en lettres arabes, CC BY-NC-SA 4.0)
      - tunizi     : corpus TUNIZI (3 000 commentaires en arabizi tunisien)
      - tsac       : corpus TSAC (17 000 commentaires tunisiens, lettres arabes et latines, LGPL-3.0)
 3. Ajoute les orthographes arabizi REELLEMENT vues dans TArC pour chaque mot tunisien.
 4. Donne un statut a chaque forme et a chaque concept, puis ecrit CSV + JSON.

Rien n'est invente : une forme vue nulle part reste dans le fichier mais avec le
statut "a_valider_locuteur".
"""
import argparse, collections, csv, json, os, re, sys, unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from candidats import CANDIDATS  # noqa: E402

RACINE = os.path.dirname(ICI)
SOURCES = os.path.join(RACINE, "sources")

# ---------------------------------------------------------------- normalisation
TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def norm_ar(t):
    """Arabe : retire voyelles/shadda/tatweel, unifie alif et ya."""
    t = TASHKEEL.sub("", t)
    t = re.sub("[إأآٱ]", "ا", t)
    return t  # on garde ى / ي distincts (sinon مرسى "port" = مرسي "merci")


def norm_lat(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def est_arabe(t):
    return bool(re.search(r"[؀-ۿ]", t))


def tokens(texte):
    texte = norm_ar(norm_lat(texte))
    return re.findall(r"[a-z0-9]+|[ء-ي]+", texte)


PREFIXES_AR = ("وال", "بال", "فال", "لل", "ال", "و", "ب", "ف", "ل")


def variantes_ar(mot):
    """Un mot arabe peut porter un prefixe colle (ال, و, ب...)."""
    yield mot
    for p in PREFIXES_AR:
        if mot.startswith(p) and len(mot) - len(p) >= 2:
            yield mot[len(p):]


class Corpus:
    """Compte les mots et les suites de mots d'un ensemble de phrases."""

    def __init__(self, nom, phrases):
        self.nom = nom
        self.phrases = [tokens(p) for p in phrases]
        self.uni = collections.Counter()
        self.uni_ar_racine = collections.Counter()
        for ph in self.phrases:
            for w in ph:
                self.uni[w] += 1
                if est_arabe(w):
                    for v in set(variantes_ar(w)):
                        if v != w:
                            self.uni_ar_racine[v] += 1
        self.texte = [" " + " ".join(ph) + " " for ph in self.phrases]

    def compte(self, forme):
        tk = tokens(forme)
        if not tk:
            return 0, []
        if len(tk) == 1:
            w = tk[0]
            n = self.uni[w] + (self.uni_ar_racine[w] if est_arabe(w) else 0)
        else:
            cible = " " + " ".join(tk) + " "
            n = sum(t.count(cible) for t in self.texte)
        ex = []
        if n:
            for ph, t in zip(self.phrases, self.texte):
                if (len(tk) == 1 and (tk[0] in ph or (est_arabe(tk[0]) and any(tk[0] in set(variantes_ar(x)) for x in ph)))) \
                        or (len(tk) > 1 and " " + " ".join(tk) + " " in t):
                    ex.append(" ".join(ph)[:160])
                    if len(ex) >= 2:
                        break
        return n, ex


# ---------------------------------------------------------------- chargement
def charger_sources():
    from dalila.config import DONNEES, db
    with db("root").cursor() as cur:
        cur.execute("SELECT question FROM chatbot_logs ORDER BY id")
        questions = [r["question"] for r in cur.fetchall() if r["question"]]

    ar_afi = []
    with open(os.path.join(DONNEES, "corpus", "passages.jsonl"), encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            if d.get("langue") == "ar":
                ar_afi.append(d.get("texte", ""))

    tarc_rows = list(csv.DictReader(open(os.path.join(SOURCES, "tarc.tsv"), encoding="utf-8"), delimiter="\t"))
    tarc_phr, cur = [], []
    for r in tarc_rows:
        if r["data"] == "<eos>":
            if cur:
                tarc_phr.append(" ".join(cur))
            cur = []
        elif r["class"] == "arabizi":
            cur.append(r["arabish"])
    tunizi = [l.split(";", 1)[1] for l in open(os.path.join(SOURCES, "tunizi.txt"), encoding="utf-8") if ";" in l]
    tsac = []
    for n in ("train_pos", "train_neg", "test_pos", "test_neg"):
        tsac += open(os.path.join(SOURCES, f"tsac_{n}.txt"), encoding="utf-8").read().splitlines()

    # Correspondance arabizi -> lettres arabes observee dans TArC
    tarc_pairs = collections.defaultdict(collections.Counter)   # mot arabe (CODA) -> {arabizi: n}
    tarc_lemme = collections.defaultdict(collections.Counter)   # lemme -> {arabizi: n}
    for r in tarc_rows:
        if r["class"] != "arabizi" or r["data"] == "<eos>":
            continue
        az = norm_lat(r["arabish"]).strip(".,!?;:\"'()")
        if not re.fullmatch(r"[a-z0-9']+", az or "-"):
            continue
        coda = norm_ar(r["CODA"].strip())
        tarc_pairs[coda][az] += 1
        for part in r["token"].split("+"):
            tarc_pairs.setdefault(norm_ar(part), collections.Counter())
        tarc_lemme[norm_ar(r["lemma"])][az] += 1
    return dict(questions=questions, ar_afi=ar_afi, tarc_phr=tarc_phr, tunizi=tunizi, tsac=tsac,
                tarc_pairs=tarc_pairs, tarc_lemme=tarc_lemme, tarc_rows=tarc_rows)


# Exemples cites mot pour mot par le cahier des charges officiel du hackathon
CDC = "Cahier des charges — Hackathon AGENTIC Agent IA AFI (Dalila).pdf"
CDC_CITATIONS = [
    ("n7eb terrain f Sfax", 7), ("3andi projet sardine", 7), ("عندي مشروع سردين", 7),
    ("terrain plot أرض 9at3a", 8), ("n7eb 3andi", 18),
]

# formes trop courtes ou identiques a un mot francais / anglais : comptage peu fiable
AMBIGUS = {"habit", "lel", "lella", "aya", "ay", "ech", "fe", "f", "fi", "ma", "me", "la", "le", "fin", "win", "ach", "tham", "som", "por", "port", "train",
           "credit", "contrat", "dossier", "projet", "usine", "zone", "zon", "gaz", "mina", "talab",
           "jiha", "ey", "taw", "lé", "lala", "metre", "ard", "matlab", "dou", "kra", "kre", "andi",
           "triko", "textile", "permis", "demande", "procedure", "subvention", "avantage", "enchere",
           "emballage", "sardine", "agro", "airport", "aeroport", "autoroute", "la gare", "plastique",
           "plastic", "depot", "merci", "mercii", "sahel", "steg", "sonede", "hectar", "m2", "fel", "fil"}


def statut_forme(c):
    if c.get("conv_afi"):
        return "vu_conversations_afi"
    if c.get("cdc_afi"):
        return "vu_cahier_des_charges_afi"
    if c.get("ar_afi"):
        return "vu_textes_afi"
    tot = sum(c.get(k, 0) for k in ("tarc", "tunizi", "tsac"))
    if tot >= 3:
        return "vu_corpus_public"
    if tot >= 1:
        return "rare_corpus_public_a_valider"
    return "a_valider_locuteur"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=RACINE)
    a = ap.parse_args()

    S = charger_sources()
    corpus = {
        "conv_afi": Corpus("conv_afi", S["questions"]),
        "ar_afi": Corpus("ar_afi", S["ar_afi"]),
        "tarc": Corpus("tarc", S["tarc_phr"]),
        "tunizi": Corpus("tunizi", S["tunizi"]),
        "tsac": Corpus("tsac", S["tsac"]),
    }
    cdc_tokens = {}
    for phrase, page in CDC_CITATIONS:
        for w in tokens(phrase):
            cdc_tokens.setdefault(w, page)

    def preuve(forme, quelles):
        res, ex = {}, {}
        for k in quelles:
            n, e = corpus[k].compte(forme)
            if n:
                res[k] = n
                ex[k] = e
        tk = tokens(forme)
        if tk and all(w in cdc_tokens for w in tk):
            res["cdc_afi"] = f"page {cdc_tokens[tk[0]]}"
        return res, ex

    lexique, lignes_csv, variantes_rows = [], [], []
    for c in CANDIDATS:
        entree = dict(id=c["id"], categorie=c["cat"], francais=c["fr"], anglais=c["en"],
                      arabe_standard=[], tunisien_arabe=[], arabizi=[], francais_melange=[])

        for f in c["msa"]:
            p, ex = preuve(f, ["ar_afi", "conv_afi"])
            entree["arabe_standard"].append(dict(forme=f, preuves=p, statut=statut_forme(p) if p else "a_valider_locuteur",
                                                 exemple=(ex.get("ar_afi") or ex.get("conv_afi") or [""])[0]))
        for f in c["tn"]:
            p, ex = preuve(f, ["conv_afi", "tsac", "ar_afi"])
            fn = norm_ar(f)
            vus_tarc = S["tarc_pairs"].get(fn, collections.Counter())
            if vus_tarc:
                p["tarc"] = sum(vus_tarc.values())
            ortho = [w for w, n in vus_tarc.most_common() if n >= 3][:8]
            if "ar_afi" in p and set(p) <= {"ar_afi"}:
                st = "vu_textes_afi_seulement"  # mot arabe present dans les textes officiels, pas forcement dialectal
            else:
                st = statut_forme({k: v for k, v in p.items() if k != "ar_afi"})
            entree["tunisien_arabe"].append(dict(forme=f, preuves=p, statut=st, arabizi_vus_dans_tarc=ortho,
                                                 exemple=(ex.get("conv_afi") or ex.get("tsac") or [""])[0]))
            for w, n in vus_tarc.most_common():
                variantes_rows.append([c["id"], f, w, n])

        # arabizi : propositions + orthographes vues dans TArC pour les mots tunisiens
        proposes = list(dict.fromkeys(norm_lat(x) for x in c["az"]))
        venus_tarc = []
        for t in entree["tunisien_arabe"]:
            for w in t["arabizi_vus_dans_tarc"]:
                if w not in proposes and w not in venus_tarc and w not in AMBIGUS:
                    venus_tarc.append(w)
        for f in proposes + venus_tarc:
            p, ex = preuve(f, ["conv_afi", "tarc", "tunizi", "tsac"])
            origine = "propose" if f in proposes else "ajoute_depuis_tarc"
            st = statut_forme(p)
            entree["arabizi"].append(dict(forme=f, preuves=p, statut=st, origine=origine,
                                          ambigu=f in AMBIGUS or len(f) <= 2,
                                          exemple=(ex.get("conv_afi") or ex.get("tunizi") or ex.get("tarc") or ex.get("tsac") or [""])[0]))
        for f in c["fr_tn"]:
            p, ex = preuve(f, ["conv_afi", "tarc", "tunizi", "tsac"])
            entree["francais_melange"].append(dict(forme=f, preuves=p, statut=statut_forme(p) if p else "a_valider_locuteur"))

        # statut global du concept
        dial = entree["tunisien_arabe"] + entree["arabizi"]
        sts = {x["statut"] for x in dial if not x.get("ambigu")}
        if {"vu_conversations_afi", "vu_cahier_des_charges_afi"} & sts:
            g = "atteste_donnees_afi"
        elif "vu_corpus_public" in sts:
            g = "atteste_corpus_public"
        else:
            g = "a_valider_locuteur"
        entree["statut"] = g
        entree["msa_atteste_afi"] = any("ar_afi" in x["preuves"] for x in entree["arabe_standard"])
        lexique.append(entree)

        def fmt(lst, garder=lambda x: True):
            return " | ".join(x["forme"] for x in lst if garder(x))

        ok = lambda x: not x["statut"].startswith(("a_valider", "rare"))
        lignes_csv.append([
            c["id"], c["cat"], " | ".join(c["fr"]), c["en"],
            " | ".join(x["forme"] + ("" if "ar_afi" in x["preuves"] else " (non vu dans textes AFI)") for x in entree["arabe_standard"]),
            fmt(entree["tunisien_arabe"], ok), fmt(entree["arabizi"], ok),
            fmt(entree["francais_melange"], ok),
            fmt(entree["tunisien_arabe"] + entree["arabizi"], lambda x: not ok(x)),
            g,
            "; ".join(sorted({k for x in dial + entree["arabe_standard"] for k in x["preuves"]})),
        ])

    os.makedirs(a.sortie, exist_ok=True)
    meta = dict(
        titre="Lexique tunisien de Dalila (darija + arabizi), domaine foncier industriel",
        genere_par="outils/construire_lexique.py",
        sources=dict(
            conv_afi="base AFI, table chatbot_logs (questions reelles des visiteurs)",
            cdc_afi=CDC + " (exemples cites p.7, 8, 18, 20)",
            ar_afi="donnees/corpus/passages.jsonl, passages en arabe (sites officiels AFI/APII/TIA/FIPA)",
            tarc="TArC, Tunisian Arabish Corpus, github.com/eligugliotta/tarc, CC BY-NC-SA 4.0 (transcription en lettres arabes semi-automatique)",
            tunizi="TUNIZI, github.com/chaymafourati/TUNIZI-Sentiment-Analysis-Tunisian-Arabizi-Dataset (iCompass)",
            tsac="TSAC, github.com/fbougares/TSAC, LGPL-3.0",
        ),
        statuts=dict(
            vu_conversations_afi="la forme apparait dans une vraie question d'un visiteur de Dalila",
            vu_cahier_des_charges_afi="la forme est citee dans le cahier des charges officiel",
            vu_textes_afi="la forme apparait dans les textes arabes de l'AFI (arabe standard)",
            vu_textes_afi_seulement="mot arabe vu dans les textes officiels, rien ne prouve qu'il soit dialectal",
            vu_corpus_public="la forme apparait au moins 3 fois dans TArC, TUNIZI ou TSAC (vrais textes tunisiens)",
            rare_corpus_public_a_valider="vue 1 ou 2 fois seulement dans les corpus publics : a faire valider",
            a_valider_locuteur="connaissance generale, vue dans aucune source : a faire valider par un locuteur tunisien",
        ),
        regle_arabizi="3 = ع, 7 = ح, 9 = ق (cahier des charges p.20) ; autres chiffres : voir correspondance_arabizi.csv",
    )
    json.dump(dict(meta=meta, concepts=lexique), open(os.path.join(a.sortie, "lexique_tunisien.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(a.sortie, "lexique_tunisien.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "categorie", "francais", "anglais", "arabe_standard",
                    "tunisien_lettres_arabes (attesté)", "arabizi (attesté)", "mots_francais_melanges (attestés)",
                    "formes_a_valider_par_un_locuteur", "statut", "sources"])
        w.writerows(lignes_csv)
    with open(os.path.join(a.sortie, "variantes_arabizi_tarc.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["concept", "mot_tunisien_arabe", "orthographe_arabizi_vue_dans_TArC", "occurrences"])
        w.writerows(variantes_rows)
    correspondance(S["tarc_rows"], a.sortie)
    translitteration(S["tarc_rows"], a.sortie)
    print(f"{len(lexique)} concepts ecrits dans {a.sortie}")
    print(collections.Counter(e["statut"] for e in lexique))


# ------------------------------------------------ chiffres arabizi -> lettres arabes
def correspondance(rows, sortie):
    """Pour chaque chiffre utilise comme lettre, mesure dans TArC la lettre arabe qu'il represente."""
    import difflib
    stats = collections.defaultdict(collections.Counter)
    simple = str.maketrans({"a": "", "e": "", "i": "", "o": "", "u": ""})
    for r in rows:
        if r["class"] != "arabizi" or r["data"] == "<eos>":
            continue
        az = norm_lat(r["arabish"])
        coda = norm_ar(r["CODA"]).replace(" ", "")
        if not re.search(r"[2-9]", az) or not coda or re.search(r"[0-9]", coda) or not re.fullmatch(r"[a-z0-9]+", az):
            continue
        cons = az.translate(simple)
        # alignement grossier : meme nombre de "consonnes" que de lettres arabes non voyelles
        ar = re.sub("[اوي]", "", coda)
        if len(cons) == len(ar):
            for ch, a in zip(cons, ar):
                if ch.isdigit():
                    stats[ch]["ء" if a in "ءؤئ" else a] += 1  # hamza, quel que soit son support
    with open(os.path.join(sortie, "correspondance_arabizi.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chiffre_arabizi", "lettre_arabe_la_plus_frequente", "part", "autres_lettres_vues", "nb_exemples_alignes", "fiabilite", "source"])
        for ch in sorted(stats):
            tot = sum(stats[ch].values())
            (a1, n1), *rest = stats[ch].most_common()
            w.writerow([ch, a1, f"{n1 / tot:.0%}", " ".join(f"{x}({n})" for x, n in rest[:3]), tot,
                        "bonne" if tot >= 50 else "faible (peu d'exemples)",
                        "TArC (+ cahier des charges p.20 pour 3, 7, 9)"])


def translitteration(rows, sortie):
    """Dictionnaire arabizi -> lettres arabes, appris mot a mot sur TArC (vraies transcriptions)."""
    d = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["class"] != "arabizi" or r["data"] == "<eos>":
            continue
        az = norm_lat(r["arabish"]).strip(".,!?;:\"'()")
        if re.fullmatch(r"[a-z0-9']+", az or "-") and not az.isdigit() and r["CODA"].strip():
            d[az][r["CODA"].strip()] += 1
    with open(os.path.join(sortie, "translitteration_arabizi_tarc.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arabizi", "lettres_arabes", "occurrences", "part"])
        for az in sorted(d):
            (ar, n), tot = d[az].most_common(1)[0], sum(d[az].values())
            w.writerow([az, ar, tot, f"{n / tot:.0%}"])


if __name__ == "__main__":
    main()
