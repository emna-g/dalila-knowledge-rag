"""Outil conseiller : qualifier un projet et donner un guide complet et sourcé (BF31, BF33, BF20).

    conseiller(secteur="huile d'olive", lieu="Sfax", surface_m2=3000, investissement_dt=2_000_000, emplois=20)

Un seul appel rend tout ce que le cahier des charges attend d'un projet décrit :
1. l'activité de la nomenclature et son secteur (graphe, par le sens : graphe.conseiller) ;
2. l'organisme compétent pour le montant donné (APII sous 15 MDT, TIA à partir de 15 MDT : texte officiel de la TIA,
   repris dans le graphe ; APIA pour l'agriculture et la pêche) ;
3. jusqu'à 3 zones du lieu (ou proches de l'infrastructure utile au secteur) qui ont des lots de la surface demandée,
   avec leur prix, le développement régional, le prix subventionné et le cahier des charges ;
4. les incitations qui s'appliquent (textes officiels, avec leur lien) ;
5. la démarche d'acquisition de l'AFI (lieu de dépôt, critères d'attribution dont l'emploi, lien).
Rien n'est estimé : chaque chiffre vient d'un outil de lecture de la base ou d'un texte cité. Les champs manquants
(lieu, surface, montant) réduisent le guide, sans rien inventer.
"""
from pydantic import BaseModel, Field
from dalila.traitement.base import Source
from dalila.traitement.graphe import Activite, EntreeConseil, Organisme, conseiller as conseiller_graphe
from dalila.traitement.lieux import LieuPossible

SEUIL_TIA_DT = 15_000_000   # « coût d'investissement supérieur ou égal à 15 MDT » (TIA, parcours de l'investisseur)
SOURCE_SEUIL = Source(titre="TIA : parcours de l'investisseur (seuil de 15 MDT entre APII et TIA)",
                      url="https://tia.gov.tn/fr/guide-de-linvestisseur/parcours-de-linvestisseur/")
ZONES_MAX, CANDIDATES_MAX = 3, 10
SURFACE_PROCHE = 0.8        # « environ 3 000 m² » : lots d'au moins 80 % de la surface demandée


class EntreeProjet(EntreeConseil):
    lieu: str | None = Field(None, max_length=100, description="gouvernorat, région ou zone voulue, tel qu'écrit")
    surface_m2: float | None = Field(None, gt=0, description="surface de terrain voulue, en m²")
    investissement_dt: float | None = Field(None, gt=0, description="coût d'investissement prévu, en dinars")
    emplois: int | None = Field(None, gt=0, description="nombre d'emplois prévus")


class ZoneProposee(BaseModel):
    zone_id: str
    nom: str
    gouvernorat: str
    lots_adaptes: int = Field(description="lots disponibles de la surface demandée (ou tous si pas de surface)")
    prix_m2_dt: float | None
    prix_m2_subventionne_dt: float | None = None
    developpement_regional: bool
    groupe_developpement_regional: int | None = None
    cahier_des_charges: str | None = Field(None, description="lien du cahier des charges de la zone")
    km: float | None = Field(None, description="distance à l'infrastructure utile, si la zone a été choisie pour elle")


class Incitation(BaseModel):
    titre: str | None
    extrait: str
    lien: str | None


class ResultatProjet(BaseModel):
    activites: list[Activite]
    secteurs: list[str]
    organismes: list[Organisme]
    organisme_competent: list[str] = Field(description="organisme(s) pour ce projet, d'après le montant s'il est donné")
    raison_organisme: str | None = None
    zones: list[ZoneProposee] = Field(default_factory=list)
    lieux_a_proposer: list[LieuPossible] = Field(default_factory=list)
    incitations: list[Incitation] = Field(default_factory=list)
    demarche_lieu_depot: str | None = None
    demarche_criteres: str | None = Field(None, description="critères d'attribution de l'AFI (texte de l'AFI)")
    emplois: int | None = None
    infrastructures_utiles: list[str]
    note: str | None = None
    sources: list[Source]


def _organismes(base, investissement):
    ids = [o.id for o in base.organismes]
    if investissement is None or not ({"APII", "TIA"} & set(ids)):
        return ids, ("Selon le coût d'investissement : APII sous 15 MDT, TIA à partir de 15 MDT."
                     if {"APII", "TIA"} <= set(ids) else None)
    retenu = "TIA" if investissement >= SEUIL_TIA_DT else "APII"
    autres = [i for i in ids if i not in ("APII", "TIA")]  # APIA (agriculture, pêche) reste compétent
    return [retenu] + autres, (f"Coût d'investissement de {investissement:,.0f} DT".replace(",", " ")
                               + (" : 15 MDT ou plus, donc la TIA." if retenu == "TIA" else " : moins de 15 MDT, donc l'APII."))


def _zones(e, infra):
    from dalila.traitement.lots import EntreeLots, chercher_lots
    from dalila.traitement.zones import (EntreeFiche, EntreeListeZones, EntreeProximite, fiche_zone, lister_zones,
                                         zones_proches)
    lieux, kms = [], {}
    if e.lieu:
        r = lister_zones(EntreeListeZones(lieu=e.lieu))
        if r.lieux_a_proposer:
            return [], r.lieux_a_proposer
        candidates = r.zones
    elif infra:
        r = zones_proches(EntreeProximite(type=infra[0], distance_max_km=50))
        candidates, kms = r.zones, {z.zone_id: z.km for z in r.zones}
    else:
        candidates = lister_zones(EntreeListeZones()).zones
    proposees = []
    for z in candidates[:CANDIDATES_MAX]:
        filtre = {"surface_min_m2": e.surface_m2 * SURFACE_PROCHE} if e.surface_m2 else {}
        n = chercher_lots(EntreeLots(zones=[z.zone_id], limite=1, **filtre)).nombre_total or 0
        if n:
            proposees.append((z, n))
    proposees.sort(key=lambda x: (x[0].prix_m2_dt is None, x[0].prix_m2_dt or 0, -x[1]))
    out = []
    for z, n in proposees[:ZONES_MAX]:
        f = fiche_zone(EntreeFiche(zone_id=z.zone_id))
        out.append(ZoneProposee(
            zone_id=z.zone_id, nom=z.nom, gouvernorat=z.gouvernorat, lots_adaptes=n,
            prix_m2_dt=f.prix_m2_dt if f and f.prix_m2_dt is not None else (f.prix_m2_dernier_publie_dt if f else None),
            prix_m2_subventionne_dt=f.prix_m2_subventionne_dt if f else None,
            developpement_regional=z.developpement_regional, groupe_developpement_regional=z.groupe_developpement_regional,
            cahier_des_charges=f.cahiers_des_charges[0].lien if f and f.cahiers_des_charges else None,
            km=kms.get(z.zone_id)))
    return out, lieux


def conseiller(e: EntreeProjet) -> ResultatProjet:
    from dalila.traitement.passages import EntreePassages, chercher_passages
    from dalila.traitement.services import EntreeDemarche, demarche
    base = conseiller_graphe(EntreeConseil(secteur=e.secteur))
    competents, raison = _organismes(base, e.investissement_dt)
    zones, lieux = _zones(e, base.infrastructures_utiles)
    sans_surface = None
    if not zones and not lieux and e.surface_m2:  # aucun lot assez grand : le dire, et montrer ce que le lieu a
        zones, _ = _zones(e.model_copy(update={"surface_m2": None}), base.infrastructures_utiles)
        if zones:
            sans_surface = (f"Aucun lot d'environ {e.surface_m2:,.0f} m² ou plus".replace(",", " ")
                            + (f" à {e.lieu}" if e.lieu else "") + " : zones du lieu avec leurs lots disponibles, de "
                            "toutes surfaces.")
    sources = list(base.sources)
    if e.investissement_dt is not None and {"APII", "TIA"} & set(competents):
        sources.append(SOURCE_SEUIL)
    regional = any(z.developpement_regional for z in zones)
    q = ("incitations et prime pour l'acquisition de terrains industriels en zone de développement régional" if regional
         else f"incitations à l'investissement industriel, {base.secteurs[0] if base.secteurs else e.secteur}")
    ps = chercher_passages(EntreePassages(question=q, nombre=3, regime="developpement_regional" if regional else None))
    vus, incitations = set(), []
    for p in ps.passages:  # une page citée une fois
        if (p.titre, p.lien) not in vus:
            vus.add((p.titre, p.lien))
            incitations.append(Incitation(titre=p.titre, extrait=p.texte[:400], lien=p.lien))
    d = demarche(EntreeDemarche(service="acquisition"))
    criteres = next((r.texte for r in d.reponses_afi if "critères" in r.texte.lower()), None)
    if criteres:
        i = criteres.lower().find("critères")
        criteres = criteres[i:i + 500]
    sources += [s for s in ps.sources if s.url] + [s for s in d.sources if s.url]
    note = " ".join(n for n in (base.note, sans_surface) if n) or None
    if not e.lieu and not base.infrastructures_utiles:
        note = ((note + " ") if note else "") + "Aucun lieu donné : zones les moins chères de toute la Tunisie ; " \
                                                 "demander au visiteur la région voulue."
    return ResultatProjet(activites=base.activites, secteurs=base.secteurs, organismes=base.organismes,
                          organisme_competent=competents, raison_organisme=raison, zones=zones, lieux_a_proposer=lieux,
                          incitations=incitations, demarche_lieu_depot=d.lieu_depot, demarche_criteres=criteres,
                          emplois=e.emplois, infrastructures_utiles=base.infrastructures_utiles, note=note,
                          sources=sources)
