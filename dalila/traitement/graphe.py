"""Outils du graphe de connaissances (Oxigraph) : COMPRENDRE et RAISONNER, jamais chiffrer.

    relier_concepts("chnowa lwra9 lazmin bech na5ou ma9sem")  -> pièces à fournir, lot ; service « acquisition »
    conseiller("projet de pêche")                              -> APIA (organisme compétent), port (commodité utile)

Le graphe relie les mots du visiteur aux concepts de l'ontologie dans les 6 langues (libellés, formes tunisiennes
attestées, synonymes appris) (BF17) et raisonne sur ses relations (BF20). Les chiffres et les textes à citer restent
dans MariaDB (autres outils). L'intention de la question n'est pas devinée ici : c'est l'agent qui décide.
"""
from functools import lru_cache
from pydantic import BaseModel, Field
from dalila.traitement.base import Source

DAL = "https://afi.nat.tn/ontology/dalila#"
P = ("PREFIX dal: <https://afi.nat.tn/ontology/dalila#> PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
     "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> ")
# identifiants des services dans le graphe -> noms du paramètre de l'outil demarche
SERVICES = {"acquisition_lot": "acquisition", "vente_encheres": "encheres",
            "attestation_situation_fonciere": "situation_fonciere",
            "attestation_insertion_hypotheque": "insertion_hypotheque", "attestation_mainlevee": "mainlevee",
            "acte_precision_contrat_final": "acte_precision", "autorisation_vente_leasing": "autorisation_vente",
            "copie_conforme": "copie_conforme"}
SOURCE_GRAPHE = Source(titre="Graphe de connaissances de Dalila (ontologie et faits tirés des données de l'AFI)")


@lru_cache(maxsize=1)
def _comprendre():
    from dalila.semantique.comprendre import Comprendre
    return Comprendre()


@lru_cache(maxsize=1)
def _familles():
    """classe -> famille de concepts (les 9 familles du cahier des charges, plus le lot)."""
    rows = _comprendre().store.query(P + "SELECT ?c ?f WHERE { ?c rdfs:subClassOf* ?f . ?f dal:famille true }",
                                     use_default_graph_as_union=True)
    return {r["c"].value.rsplit("#", 1)[-1]: r["f"].value.rsplit("#", 1)[-1] for r in rows}


def _sparql(requete):
    return list(_comprendre().store.query(P + requete, use_default_graph_as_union=True))


def _id(uri):
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


# ---------------------------------------------------------------- relier_concepts
class EntreeConcepts(BaseModel):
    texte: str = Field(..., max_length=500, description="la question du visiteur, telle quelle (toutes langues)")


class Concept(BaseModel):
    id: str
    libelle: str
    famille: str = Field(description="Lieu, Lot, SecteurActivite, Commodite, Demarche, Incitation, Organisme, Projet, "
                                     "ServiceAFI ou Document")
    type: str


class ResultatConcepts(BaseModel):
    concepts: list[Concept]
    services_afi: list[str] = Field(description="services reconnus, à passer à l'outil demarche")
    sources: list[Source]


def _trouves(texte):
    c = _comprendre()
    from dalila.semantique.comprendre import norm
    mots, trouves = norm(texte).split(), set()
    for n in range(min(8, len(mots)), 0, -1):
        for i in range(len(mots) - n + 1):
            fen = " ".join(mots[i:i + n])
            if len(fen) < 3:  # un mot de 1 ou 2 lettres n'est pas un concept (« me », « de »)
                continue
            trouves |= c.libelles.get(fen, set())
            if n >= 2:
                trouves |= c.zones_mots.get(fen, set())
    import difflib
    for m in mots:  # petites fautes : « comodites » ~ « commodites »
        if len(m) >= 5 and m not in c.libelles:
            proche = difflib.get_close_matches(m, c.vocab, n=1, cutoff=0.86)
            if proche:
                trouves |= c.libelles[proche[0]]
    return trouves


def relier_concepts(e: EntreeConcepts) -> ResultatConcepts:
    c, fam = _comprendre(), _familles()
    out, services = [], []
    for s in sorted(_trouves(e.texte)):
        types = c.types.get(s, set())
        t = next((x for x in sorted(types) if x in fam), None)
        if t is None and s.startswith(DAL):  # le concept est une classe de l'ontologie (« Pièce à fournir »…)
            t = s.rsplit("#", 1)[-1] if s.rsplit("#", 1)[-1] in fam else None
        if t is None:
            continue
        out.append(Concept(id=_id(s), libelle=c.label(s), famille=fam[t], type=t))
        if "ServiceAFI" in types and _id(s) in SERVICES:
            services.append(SERVICES[_id(s)])
    return ResultatConcepts(concepts=out[:25], services_afi=sorted(set(services)), sources=[SOURCE_GRAPHE])


# ---------------------------------------------------------------- conseiller
class EntreeConseil(BaseModel):
    secteur: str = Field(..., max_length=200, description="l'activité du projet décrit par le visiteur, reformulée en "
                                                         "français avec des mots de métier (quelques mots)")


class Lien(BaseModel):
    de: str
    relation: str
    vers: str


class Organisme(BaseModel):
    id: str
    nom: str
    role: str | None = Field(None, description="ce dont il s'occupe, d'après le texte officiel cité")


class Activite(BaseModel):
    libelle: str
    secteur: str
    proximite: float = Field(description="proximité de sens avec la description du visiteur (0 à 1)")


class ResultatConseil(BaseModel):
    activites: list[Activite] = Field(description="activités de la nomenclature les plus proches, à confirmer avec le "
                                                  "visiteur si plusieurs secteurs différents")
    secteurs: list[str]
    organismes: list[Organisme] = Field(description="organismes compétents, avec leur rôle (seuil d'investissement…)")
    infrastructures_utiles: list[str] = Field(description="types à passer à l'outil zones_proches (ex. port)")
    raccordements_necessaires: list[str] = Field(description="équipements de zone à vérifier dans fiche_zone")
    explication: list[Lien]
    note: str | None = None
    sources: list[Source]


NB_CANDIDATES = 5   # activités proposées à l'agent (la bonne est dans les 5 premières : 12 cas sur 12, mesuré)
ECART_SUR = 0.03    # sous cet écart entre deux secteurs, le choix est incertain : l'agent confirme avec le visiteur


@lru_cache(maxsize=1)
def _index_activites():
    """Secteurs et activités, indexés « libellé (secteur : …) » : le secteur aide le modèle à distinguer des libellés
    courts. Vecteurs calculés une fois avec le modèle de recherche."""
    from dalila.moteurs.embeddings import encoder_textes
    c = _comprendre()
    noeuds = sorted({s for ss in c.libelles.values() for s in ss
                     if c.types.get(s, set()) & {"SecteurActivite", "Activite"}})
    libelles, secteurs = [c.label(s) for s in noeuds], []
    for s in noeuds:
        r = _sparql(f"SELECT ?sec WHERE {{ <{s}> dal:dansSecteur ?sec }}")
        secteurs.append(r[0]["sec"].value if r else s)
    textes = [l if sec == s else f"{l} (secteur : {c.label(sec)})" for s, l, sec in zip(noeuds, libelles, secteurs)]
    return noeuds, libelles, secteurs, encoder_textes(textes)


def _synonymes_appris():
    """Synonymes appris des conversations (dalila/apprentissage/synonymes_appris.py), actifs : ((terme, noeud), …) et
    une version qui change à chaque publication ou annulation. Table absente : rien."""
    try:
        from dalila.traitement.base import q
        lignes = q("SELECT terme, concept_uri FROM agent_appris_synonymes WHERE actif = 1 ORDER BY id")
        v = q("SELECT COUNT(*) n, MAX(modifie_le) m FROM agent_appris_synonymes")[0]
        return tuple((l["terme"], l["concept_uri"]) for l in lignes), (v["n"], str(v["m"]))
    except Exception:  # noqa: BLE001
        return (), None


@lru_cache(maxsize=2)
def _index_appris(appris, version):
    """Chaque synonyme appris devient une entrée de plus de l'index : le terme du visiteur mène à son activité."""
    if not appris:
        return [], [], [], None
    from dalila.moteurs.embeddings import encoder_textes
    noeuds, libelles, secteurs, _ = _index_activites()
    pos = {n: i for i, n in enumerate(noeuds)}
    garde = [(t, n) for t, n in appris if n in pos]
    if not garde:
        return [], [], [], None
    return ([n for _, n in garde], [libelles[pos[n]] for _, n in garde], [secteurs[pos[n]] for _, n in garde],
            encoder_textes([t for t, _ in garde]))


def _activites(texte, k=NB_CANDIDATES):
    """Les k activités ou secteurs les plus proches PAR LE SENS : (noeud, libellé, secteur, proximité). Les synonymes
    appris sont des entrées de plus ; une activité n'est rendue qu'une fois (sa meilleure proximité)."""
    import numpy as np
    from dalila.moteurs.embeddings import encoder_questions
    noeuds, libelles, secteurs, vecs = _index_activites()
    an, al, asec, avecs = _index_appris(*_synonymes_appris())
    if avecs is not None:
        noeuds, libelles, secteurs, vecs = noeuds + an, libelles + al, secteurs + asec, np.vstack([vecs, avecs])
    sims = vecs @ encoder_questions([texte])[0]
    out, vus = [], set()
    for i in sims.argsort()[::-1]:
        if noeuds[i] not in vus:
            vus.add(noeuds[i])
            out.append((noeuds[i], libelles[i], secteurs[i], float(sims[i])))
        if len(out) == k:
            break
    return out


def conseiller(e: EntreeConseil) -> ResultatConseil:
    c = _comprendre()
    proches = _activites(e.secteur)
    activites = [Activite(libelle=lib, secteur=c.label(sec), proximite=round(sim, 2)) for _, lib, sec, sim in proches]
    liens = [Lien(de=lib, relation="fait partie du secteur", vers=c.label(sec)) for n, lib, sec, _ in proches[:1] if n != sec]
    meilleur = proches[0][3]
    secteurs = {}
    for _, _, sec, sim in proches:  # le secteur de la meilleure activité, et ceux presque aussi proches
        if sim >= meilleur - ECART_SUR:
            secteurs.setdefault(sec, sim)
    organismes, infra, racc = {}, set(), set()
    for sec in secteurs:
        for r in _sparql(f"SELECT ?o ?d WHERE {{ <{sec}> dal:organismeCompetent ?o . OPTIONAL {{ ?o "
                         f"<http://purl.org/dc/terms/description> ?d }} }}"):
            o = _id(r["o"].value)
            organismes[o] = Organisme(id=o, nom=c.label(r["o"].value), role=r["d"].value if r["d"] else None)
            liens.append(Lien(de=c.label(sec), relation="organisme compétent", vers=c.label(r["o"].value)))
        for r in _sparql(f"SELECT ?x ?t WHERE {{ <{sec}> dal:commoditeUtile ?x . ?x a ?t }}"):
            x, t = _id(r["x"].value), _id(r["t"].value)
            if t == "TypeProximite":
                infra.add(x)
                liens.append(Lien(de=c.label(sec), relation="a besoin d'être proche de", vers=c.label(r["x"].value)))
            elif t == "TypeEquipement":
                racc.add(x)
    note = None
    if len(secteurs) > 1:
        note = ("Plusieurs secteurs presque aussi proches : confirmer l'activité avec le visiteur par une question à "
                "choix (liste « activites »).")
    return ResultatConseil(activites=activites, secteurs=sorted(c.label(s) for s in secteurs),
                           organismes=sorted(organismes.values(), key=lambda o: o.id),
                           infrastructures_utiles=sorted(infra), raccordements_necessaires=sorted(racc),
                           explication=liens, note=note, sources=[SOURCE_GRAPHE])
