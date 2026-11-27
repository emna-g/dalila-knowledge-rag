"""Découpage d'un texte en passages, à l'identique de la fusion (dalila_fusion/outils/build_final.py, chunks).

    decouper(texte) -> [(page, article, texte), ...]   passages d'environ MAXC caractères

Même découpage que le corpus d'origine : un passage mis à jour ressemble à ceux qu'il remplace (même taille, mêmes
coupures aux pages « === page N === » et aux articles), donc la recherche le traite de la même façon.
"""
import re

MAXC = 1400


def decouper(texte):
    page, article, buf, bpage, out = None, None, [], None, []
    for para in re.split(r"\n\s*\n", texte):
        p = para.strip()
        mp = re.match(r"=== page (\d+)", p)
        if mp:
            page = int(mp.group(1))
            p = re.sub(r"^=== page .*?===\s*", "", p)
            if not p:
                continue
        ma = re.match(r"(?i)^(article\s+[\w\-]+|titre\s+[\w]+|الفصل\s+\S+)", p)
        if ma and buf and sum(len(b) for b in buf) > 300:
            out.append((bpage, article, "\n".join(buf)))
            buf = []
        if ma:
            article = ma.group(1)
        if buf and sum(len(b) for b in buf) + len(p) > MAXC:
            out.append((bpage, article, "\n".join(buf)))
            buf = []
        if not buf:
            bpage = page
        while len(p) > MAXC:  # paragraphe très long
            out.append((page, article, p[:MAXC]))
            p = p[MAXC:]
        buf.append(p)
    if buf:
        out.append((bpage, article, "\n".join(buf)))
    return [(pg, ar, t) for pg, ar, t in out if len(re.sub(r"\W", "", t)) > 60]


def paragraphes(texte):
    """Texte d'une page web (une ligne par bloc) -> paragraphes séparés par une ligne vide, comme dans la fusion."""
    return "\n\n".join(l for l in texte.splitlines() if l.strip())


def langue(texte):
    """« ar » si le passage a plus de lettres arabes que latines, sinon « fr » (règle de la fusion, has_ar)."""
    return "ar" if len(re.findall(r"[؀-ۿ]", texte)) > len(re.findall(r"[A-Za-z]", texte)) else "fr"


# règle de la fusion (outils/fusion/fusion.py) : un montant, une surface ou un pourcentage
CHIFFRE = re.compile(r"\d[\d\s.,]*\s?(DT|dinars?|TND|m²|m2|ha|%|millions?|MD|دينار|بالمائة)", re.I)


def contient_chiffre(texte):
    return bool(CHIFFRE.search(texte))
