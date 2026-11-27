"""Outils sur les zones : fiche_zone, lister_zones, zones_proches. Tout est lu dans les vues v_pub_*."""
from typing import Literal
from pydantic import BaseModel, Field
from dalila.traitement.base import SOURCE_BASE, Source, nombre, q
from dalila.traitement.lieux import LieuPossible, lieu_unique

Infrastructure = Literal["aeroport", "port", "gare", "autoroute", "gazoduc"]


class EntreeFiche(BaseModel):
    zone_id: str = Field(..., max_length=100, description="code de la zone, ou son nom tel que le visiteur l'a écrit")


class Distance(BaseModel):
    type: str
    nom: str | None
    km: float


class Document(BaseModel):
    titre: str
    lien: str


class FicheZone(BaseModel):
    zone_id: str
    nom: str
    nom_ar: str | None
    gouvernorat: str
    developpement_regional: bool
    groupe_developpement_regional: int | None = Field(description="1 ou 2 ; vide hors développement régional")
    prix_m2_dt: float | None = Field(description="prix actuel de l'AFI ; vide : l'AFI ne publie pas de prix")
    prix_m2_dernier_publie_dt: float | None = Field(None, description="si pas de prix actuel : dernier prix publié par "
                                                                     "l'AFI, à dire avec sa source et « à confirmer »")
    prix_dernier_publie_source: str | None = None
    prix_m2_subventionne_dt: float | None = Field(None, description="prix au m² après la prime d'infrastructure du "
                                                                    "développement régional, publié sur le site de l'AFI")
    prix_site_afi: float | None = Field(None, description="prix au m² publié sur la page des incitations du site de l'AFI")
    prix_en_conflit: bool = Field(False, description="vrai si le site de l'AFI donne un autre prix que sa base : dire les "
                                                     "deux et conseiller de confirmer auprès de l'AFI")
    surface_totale_m2: float | None
    surface_amenagee_m2: float | None
    surface_amenagee_calculee_m2: float | None = Field(None, description="si l'AFI ne donne pas la surface aménagée : "
                                                                         "surface couverte par les contours des lots de la "
                                                                         "base AFI (calculée), à dire comme telle")
    lots_disponibles: int
    lots_disponibles_a_confirmer: int
    lots_mis_aux_encheres: int
    distances: list[Distance]
    equipements: dict[str, str] = Field(description="type -> valeur et unité (valeurs non renseignées absentes)")
    services_proches: dict[str, Distance] = Field(description="le plus proche de chaque catégorie")
    cahiers_des_charges: list[Document]
    plans_de_lotissement: list[Document]
    sources: list[Source]


def fiche_zone(e: EntreeFiche) -> FicheZone | None:
    z = q("SELECT * FROM v_pub_zones WHERE zone_id = %s", e.zone_id)
    if not z:  # un nom plutôt qu'un code : résolu seulement s'il désigne une seule zone
        from dalila.traitement.lieux import EntreeLieu, resoudre_lieu
        zs = [l for l in resoudre_lieu(EntreeLieu(texte=e.zone_id)).lieux if l.type == "zone"]
        if len(zs) != 1:
            return None
        z = q("SELECT * FROM v_pub_zones WHERE zone_id = %s", zs[0].id)
    z = z[0]
    zid = z["zone_id"]
    dist = [Distance(type=r["type"], nom=r["nom"], km=nombre(r["km"]))
            for r in q("SELECT type, nom, km FROM v_pub_zone_distances WHERE zone_id = %s ORDER BY km", zid)]
    equip = {r["type"]: f"{r['valeur']} {r['unite'] or ''}".strip()
             for r in q("SELECT type, valeur, unite FROM v_pub_zone_equipements WHERE zone_id = %s", zid)}
    serv = {}
    for r in q("SELECT categorie, nom, distance_km FROM v_pub_services_proches WHERE zone_id = %s ORDER BY distance_km", zid):
        serv.setdefault(r["categorie"], Distance(type=r["categorie"], nom=r["nom"], km=nombre(r["distance_km"])))
    cahiers = [Document(titre=f"Cahier des charges {c['zone']} {c['annee'] or ''}".strip(), lien=c["lien_pdf"])
               for c in q("SELECT zone, annee, lien_pdf FROM v_pub_cahiers WHERE zone_id = %s", zid) if c["lien_pdf"]]
    plans = [Document(titre=p["nom"], lien=p["lien"]) for p in q("SELECT nom, lien FROM v_pub_plans WHERE zone_id = %s", zid)]
    return FicheZone(zone_id=zid, nom=z["nom_fr"], nom_ar=z["nom_ar"], gouvernorat=z["gouvernorat_fr"],
                     developpement_regional=bool(z["zone_developpement_regional"]),
                     groupe_developpement_regional=z["groupe_developpement_regional"],
                     prix_m2_dt=nombre(z["prix_m2_dt"]), prix_m2_dernier_publie_dt=nombre(z["prix_m2_dernier_publie_dt"]),
                     prix_dernier_publie_source=z["prix_dernier_publie_source"],
                     prix_m2_subventionne_dt=nombre(z["prix_m2_subventionne_site_afi_dt"]),
                     prix_site_afi=nombre(z["prix_m2_site_afi_dt"]), prix_en_conflit=bool(z["prix_en_conflit"]),
                     surface_totale_m2=nombre(z["surface_totale_m2"]),
                     surface_amenagee_m2=nombre(z["surface_amenagee_m2"]), surface_amenagee_calculee_m2=nombre(z["surface_amenagee_calculee_m2"]),
                     lots_disponibles=z["lots_disponibles"],
                     lots_disponibles_a_confirmer=z["lots_disponibles_a_confirmer"],
                     lots_mis_aux_encheres=z["lots_mis_aux_encheres"], distances=dist, equipements=equip,
                     services_proches=serv, cahiers_des_charges=cahiers, plans_de_lotissement=plans,
                     sources=[SOURCE_BASE] + [Source(titre=d.titre, url=d.lien) for d in cahiers + plans]
                     + ([Source(titre="Site de l'AFI, incitations en zones de développement régional",
                                url=z["prix_site_afi_source"].split(" (")[0])] if z["prix_site_afi_source"] else []))


class EntreeListeZones(BaseModel):
    lieu: str | None = Field(None, max_length=100, description="nom du gouvernorat ou de la région tel que le visiteur "
                                                               "l'a écrit (fautes tolérées, français ou arabe)")
    gouvernorats: list[int] = Field(default_factory=list, description="codes des gouvernorats")
    regime: Literal["developpement_regional", "littoral"] | None = None
    groupe_developpement_regional: Literal[1, 2] | None = None
    seulement_avec_lots_disponibles: bool = True


class ResumeZone(BaseModel):
    zone_id: str
    nom: str
    gouvernorat: str
    prix_m2_dt: float | None
    lots_disponibles: int
    developpement_regional: bool
    groupe_developpement_regional: int | None


class ResultatZones(BaseModel):
    nombre: int | None = Field(description="nombre exact de zones ; vide si le lieu est à préciser")
    lots_disponibles_total: int | None = Field(None, description="nombre exact de lots disponibles dans ces zones")
    zones: list[ResumeZone]
    lieu_retenu: str | None = None
    lieux_a_proposer: list[LieuPossible] = Field(default_factory=list, description="lieu ambigu ou inconnu : options à "
                                                                                   "proposer au visiteur")
    sources: list[Source]


def _resume(r):
    return ResumeZone(zone_id=r["zone_id"], nom=r["nom_fr"], gouvernorat=r["gouvernorat_fr"],
                      prix_m2_dt=nombre(r["prix_m2_dt"]), lots_disponibles=r["lots_disponibles"],
                      developpement_regional=bool(r["zone_developpement_regional"]),
                      groupe_developpement_regional=r["groupe_developpement_regional"])


def lister_zones(e: EntreeListeZones) -> ResultatZones:
    retenu = None
    if e.lieu:  # le nom du lieu est résolu ici : l'agent n'enchaîne pas deux outils
        l0, options = lieu_unique(e.lieu)
        if l0 is None:
            return ResultatZones(nombre=None, zones=[], lieux_a_proposer=options, sources=[SOURCE_BASE])
        retenu = f"{l0.type} {l0.nom}"
        e = e.model_copy(update={"gouvernorats": e.gouvernorats + l0.gouvernorats})
    sql, p = "SELECT * FROM v_pub_zones WHERE 1=1", []
    if e.gouvernorats:
        sql += " AND gouvernorat_code IN (" + ",".join(["%s"] * len(e.gouvernorats)) + ")"
        p += e.gouvernorats
    if e.regime:
        sql += " AND zone_developpement_regional = %s"
        p.append(1 if e.regime == "developpement_regional" else 0)
    if e.groupe_developpement_regional:
        sql += " AND groupe_developpement_regional = %s"
        p.append(e.groupe_developpement_regional)
    if e.seulement_avec_lots_disponibles:
        sql += " AND lots_disponibles > 0"
    rows = q(sql + " ORDER BY lots_disponibles DESC, nom_fr", *p)
    return ResultatZones(nombre=len(rows), lots_disponibles_total=sum(r["lots_disponibles"] or 0 for r in rows),
                         zones=[_resume(r) for r in rows], lieu_retenu=retenu, sources=[SOURCE_BASE])


class EntreeProximite(BaseModel):
    type: Infrastructure
    distance_max_km: float = Field(30, ge=0, le=500)
    seulement_avec_lots_disponibles: bool = True


class ZoneProche(ResumeZone):
    infrastructure: str | None
    km: float


class ResultatProximite(BaseModel):
    nombre: int
    zones: list[ZoneProche]
    sources: list[Source]


def zones_proches(e: EntreeProximite) -> ResultatProximite:
    rows = q("SELECT z.*, d.nom AS infra, d.km FROM v_pub_zone_distances d JOIN v_pub_zones z USING (zone_id) "
             "WHERE d.type = %s AND d.km <= %s" + (" AND z.lots_disponibles > 0" if e.seulement_avec_lots_disponibles
                                                     else "") + " ORDER BY d.km", e.type, e.distance_max_km)
    zones = [ZoneProche(**_resume(r).model_dump(), infrastructure=r["infra"], km=nombre(r["km"])) for r in rows]
    return ResultatProximite(nombre=len(zones), zones=zones, sources=[SOURCE_BASE])
