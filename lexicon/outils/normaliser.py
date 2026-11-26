# -*- coding: utf-8 -*-
"""
Normaliseur tunisien de Dalila : a brancher AVANT la recherche RAG.

    from normaliser import NormaliseurTunisien
    n = NormaliseurTunisien()                       # lit lexique_tunisien.json
    r = n.analyser("chnowa lwra9 lazmin bech na5ou ma9sem sina3i?")
    r["tunisien"]        -> True / False (le message ressemble a du tunisien)
    r["ecriture"]        -> "arabizi" / "arabe" / "latin" / "mixte"
    r["concepts"]        -> ["papiers", "terrain", ...]
    r["requete_enrichie"]-> texte d'origine + mots francais et arabe standard des concepts
    r["en_arabe"]        -> l'arabizi converti en lettres arabes (dictionnaire TArC)

Le normaliseur n'invente rien : il n'utilise que les formes du lexique
(par defaut seulement celles qui sont attestees dans une source reelle).
"""
import csv, json, os, re, unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(ICI)
TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
PREFIXES_AR = ("وال", "بال", "فال", "لل", "ال", "و", "ب", "ف", "ل")
# chiffres-lettres mesures dans TArC (voir correspondance_arabizi.csv) ; 3, 7, 9 confirmes par le cahier des charges
CHIFFRES = {"3": "ع", "7": "ح", "9": "ق", "5": "خ", "2": "ء"}


def norm_ar(t):
    t = TASHKEEL.sub("", t)
    return re.sub("[إأآٱ]", "ا", t)


def norm_lat(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(t):
    return re.findall(r"[a-z0-9]+|[ء-ي]+", norm_ar(norm_lat(t)))


class NormaliseurTunisien:
    def __init__(self, lexique=None, translit=None, inclure_a_valider=False):
        lexique = lexique or os.path.join(RACINE, "lexique_tunisien.json")
        translit = translit or os.path.join(RACINE, "translitteration_arabizi_tarc.csv")
        data = json.load(open(lexique, encoding="utf-8"))
        self.concepts = {c["id"]: c for c in data["concepts"]}
        self.index = {}        # forme (1 ou plusieurs mots) -> set(concepts)
        self.dialecte = set()  # formes qui signalent le tunisien (pas du francais, pas de l'arabe standard)

        def ok(x):
            return inclure_a_valider or not x["statut"].startswith(("a_valider", "rare"))

        for c in data["concepts"]:
            for champ in ("tunisien_arabe", "arabizi", "arabe_standard", "francais_melange"):
                for x in c[champ]:
                    if champ != "arabe_standard" and not ok(x):
                        continue
                    cle = " ".join(tokens(x["forme"]))
                    if not cle:
                        continue
                    self.index.setdefault(cle, set()).add(c["id"])
                    if champ in ("tunisien_arabe", "arabizi") and not x.get("ambigu") and len(cle) > 2 \
                            and x["statut"] != "vu_textes_afi_seulement":
                        self.dialecte.add(cle)
            for f in c["francais"]:
                cle = " ".join(tokens(f))
                if cle:
                    self.index.setdefault(cle, set()).add(c["id"])
        # un mot francais ou arabe standard courant ne prouve pas le tunisien
        msa = {" ".join(tokens(x["forme"])) for c in data["concepts"] for x in c["arabe_standard"]}
        fr = {" ".join(tokens(f)) for c in data["concepts"] for f in c["francais"]}
        fr |= {" ".join(tokens(x["forme"])) for c in data["concepts"] for x in c["francais_melange"]}
        self.dialecte -= msa | fr
        self.max_n = max(len(k.split()) for k in self.index)

        self.translit = {}
        if os.path.exists(translit):
            for r in csv.DictReader(open(translit, encoding="utf-8-sig")):
                if int(r["occurrences"]) >= 2:
                    self.translit[r["arabizi"]] = r["lettres_arabes"]

    # ------------------------------------------------------------------
    def _chercher(self, tk):
        trouves, dial, i = [], 0, 0
        while i < len(tk):
            pris = False
            for n in range(min(self.max_n, len(tk) - i), 0, -1):
                cle = " ".join(tk[i:i + n])
                cands = [cle]
                if n == 1 and re.search(r"[ء-ي]", cle):
                    cands += [cle[len(p):] for p in PREFIXES_AR if cle.startswith(p) and len(cle) - len(p) >= 2]
                for c in cands:
                    if c in self.index:
                        trouves.append((c, sorted(self.index[c])))
                        dial += c in self.dialecte
                        i += n
                        pris = True
                        break
                if pris:
                    break
            if not pris:
                i += 1
        return trouves, dial

    def ecriture(self, texte):
        ar = bool(re.search(r"[؀-ۿ]", texte))
        lat = re.findall(r"[A-Za-z0-9']*[A-Za-z][A-Za-z0-9']*", texte)
        az = any(re.search(r"[a-z][2-9]|[2-9][a-z]", w.lower()) for w in lat)
        if ar and lat:
            return "mixte"
        if ar:
            return "arabe"
        return "arabizi" if az else "latin"

    def en_arabe(self, texte):
        """Arabizi -> lettres arabes, mot a mot, avec le dictionnaire TArC. Mot inconnu : garde tel quel."""
        out = []
        for w in re.findall(r"\S+", texte):
            cle = norm_lat(w).strip(".,!?;:\"'()")
            out.append(self.translit.get(cle, w))
        return " ".join(out)

    def analyser(self, texte):
        tk = tokens(texte)
        trouves, nb_dial = self._chercher(tk)
        ecr = self.ecriture(texte)
        concepts = []
        for _, ids in trouves:
            for i in ids:
                if i not in concepts:
                    concepts.append(i)
        # tunisien si au moins un mot dialectal, ou chiffres-lettres arabizi
        tunisien = nb_dial >= 1 or ecr == "arabizi"
        # On n'ajoute que les concepts venus d'un mot NON francais (inutile de traduire "terrain" en "terrain"),
        # et pas les petits mots ("fi", "merci", "je veux", "comment") qui noient la recherche.
        mots_fr = {" ".join(tokens(f)) for c in self.concepts.values() for f in c["francais"]}
        mots_fr |= {" ".join(tokens(x["forme"])) for c in self.concepts.values() for x in c["francais_melange"]}
        ajout = []
        for mot, ids in trouves:
            if mot in mots_fr:
                continue
            for cid in ids:
                c = self.concepts[cid]
                if c["categorie"] in ("liaison", "politesse", "intention", "question"):
                    continue
                ajout.append(c["francais"][0])
                ajout += [x["forme"] for x in c["arabe_standard"] if "ar_afi" in x["preuves"]][:1]
        return dict(texte=texte, tunisien=tunisien, ecriture=ecr, mots_trouves=[m for m, _ in trouves],
                    nb_mots_dialectaux=nb_dial, concepts=concepts,
                    requete_enrichie=(texte + " || " + " ".join(dict.fromkeys(ajout))).strip(),
                    # conseil des tests : n'enrichir que les messages tunisiens (le francais et l'arabe standard
                    # sont deja bien trouves tels quels)
                    requete_pour_rag=(texte + " || " + " ".join(dict.fromkeys(ajout))).strip() if tunisien else texte,
                    en_arabe=self.en_arabe(texte) if ecr in ("arabizi", "latin", "mixte") else texte)


if __name__ == "__main__":
    import sys
    n = NormaliseurTunisien()
    for q in sys.argv[1:] or ["chnowa lwra9 lazmin bech na5ou ma9sem sina3i?", "n7eb terrain f Sfax",
                              "3andi projet sardine", "عندي مشروع سردين", "Procédure d'acquisition ?"]:
        print(json.dumps(n.analyser(q), ensure_ascii=False, indent=1))
