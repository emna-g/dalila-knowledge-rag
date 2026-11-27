"""Relie une question aux concepts du graphe (Oxigraph) : zones, gouvernorats, commodités, services, secteurs…

    from dalila.semantique.comprendre import Comprendre
    c = Comprendre()
    c.analyser("quels sont les comodités prés de la zone industrielle sidi achour borj el amri")
    -> {"zones": [...], "gouvernorats": [...], "concepts": [...], "intention": "commodites"}

- Les libellés viennent des graphes « core », « abox » et « lexique » (formes attestées) ; pas de « a-valider ».
- Les noms de zones longs sont reconnus en entier ou en partie (« Sidi Achour »).
- Les petites fautes d'orthographe sont tolérées (« comodités », « prés »).
"""
import difflib, re, unicodedata
import pyoxigraph as ox
from dalila.config import ONTOLOGIE

DAL = "https://afi.nat.tn/ontology/dalila#"
G = "https://afi.nat.tn/ontology/dalila/graphe/"
MOTS_VIDES = set("de la le les des du d l un une et a au aux en dans pour par sur est quel quels quelle quelles sont "
                 "ce il y zone zones industrielle industrielles fi f el mel w".split())


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode() if re.search(r"[A-Za-zÀ-ÿ]", t or "") \
        else (t or "")
    return re.sub(r"[^\w؀-ۿ]+", " ", t.lower()).strip()


class Comprendre:
    def __init__(self, store=ONTOLOGIE / "store"):
        self.store = ox.Store.read_only(str(store))
        q = f"""SELECT ?s ?l ?type WHERE {{
          GRAPH ?g {{ ?s <http://www.w3.org/2004/02/skos/core#prefLabel>|<http://www.w3.org/2004/02/skos/core#altLabel>|<http://www.w3.org/2004/02/skos/core#hiddenLabel> ?l }}
          FILTER(?g IN (<{G}core>, <{G}abox>, <{G}lexique>))
          OPTIONAL {{ GRAPH ?g2 {{ ?s a ?type }} }} }}"""
        self.libelles, self.types = {}, {}
        for r in self.store.query(q, use_default_graph_as_union=False):
            s, l = r["s"].value, r["l"].value
            k = norm(l)
            if k:
                self.libelles.setdefault(k, set()).add(s)
            if r["type"] is not None:
                self.types.setdefault(s, set()).add(r["type"].value.split("#")[-1])
        # noms de zones : nom complet et morceaux significatifs (« sidi achour », « borj el amri »)
        self.zones_mots = {}
        for k, ss in self.libelles.items():
            for s in ss:
                if "ZoneIndustrielle" in self.types.get(s, set()):
                    mots = [m for m in k.split() if m not in MOTS_VIDES and len(m) > 2]
                    for n in (2, 3):
                        for i in range(len(mots) - n + 1):
                            self.zones_mots.setdefault(" ".join(mots[i:i + n]), set()).add(s)
                    if len(mots) == 1:
                        self.zones_mots.setdefault(mots[0], set()).add(s)
        self.vocab = [k for k in self.libelles if len(k) >= 5 and " " not in k]

    def label(self, s, lang="fr"):
        r = list(self.store.query(f'SELECT ?l WHERE {{ <{s}> <http://www.w3.org/2004/02/skos/core#prefLabel> ?l '
                                  f'FILTER(LANG(?l)="{lang}") }} LIMIT 1', use_default_graph_as_union=True))
        return r[0]["l"].value if r else s.rsplit("/", 1)[-1]

    def analyser(self, question):
        q = norm(question)
        mots = q.split()
        trouves = set()
        for n in range(min(8, len(mots)), 0, -1):  # du plus long au plus court
            for i in range(len(mots) - n + 1):
                fen = " ".join(mots[i:i + n])
                trouves |= self.libelles.get(fen, set())
                if n >= 2:
                    trouves |= self.zones_mots.get(fen, set())
        for m in mots:  # tolérance aux fautes : « comodites » ~ « commodites »
            if len(m) >= 5 and m not in self.libelles:
                proche = difflib.get_close_matches(m, self.vocab, n=1, cutoff=0.86)
                if proche:
                    trouves |= self.libelles[proche[0]]
        types = lambda s: self.types.get(s, set())  # noqa: E731
        zones = sorted(s for s in trouves if "ZoneIndustrielle" in types(s))
        gouvs = sorted(s for s in trouves if "Gouvernorat" in types(s))
        commodite = any(s == DAL + "Commodite" or types(s) & {"TypeProximite", "TypeEquipement", "TypeService"}
                        for s in trouves)
        demarche = any(s in (DAL + "Piece", DAL + "Procedure", DAL + "Formulaire", DAL + "Demarche")
                       or "ServiceAFI" in types(s) for s in trouves)
        activite = [s for s in trouves if "Activite" in types(s) or "SecteurActivite" in types(s)]
        cahier = any(s == DAL + "CahierDesCharges" for s in trouves) or bool(re.search(r"autoris|interdit|permis|activit", q))
        intention = ("commodites" if commodite and zones else "regles_zone" if cahier and zones
                     else "demarche" if demarche else "lots" if (zones or gouvs) else "general")
        services = sorted(s for s in trouves if "ServiceAFI" in types(s))
        fiches = set()
        for s in services:  # fiches officielles de l'AFI pour ce service (via sa procédure)
            for r in self.store.query(f"SELECT ?f WHERE {{ <{s}> <{DAL}aProcedure>/<{DAL}ficheAFI> ?f }}",
                                      use_default_graph_as_union=True):
                fiches.add(int(r["f"].value))
        return {"zones": [(s.rsplit("/", 1)[-1], self.label(s)) for s in zones],
                "services": [self.label(s) for s in services], "fiches_afi": sorted(fiches),
                "gouvernorats": [self.label(s) for s in gouvs],
                "concepts": sorted({self.label(s) for s in trouves})[:20],
                "activites": [self.label(s) for s in activite][:10],
                "intention": intention}
