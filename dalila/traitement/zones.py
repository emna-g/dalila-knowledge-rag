"""Outils sur les zones : fiche_zone, lister_zones, zones_proches. Tout est lu dans les vues v_pub_*."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from dalila.traitement.base import SOURCE_BASE, Source, nombre, q
from dalila.traitement.references import (
    derniers_prix_publies_par_zone,
    groupe_developpement_regional,
    nom_gouvernorat,
    prix_site_afi_par_zone,
)

Infrastructure = Literal["aeroport", "port", "gare", "autoroute", "gazoduc"]


class EntreeFiche(BaseModel):
    zone_id: str = Field(..., max_length=20, description="code de la zone (resoudre_lieu)")


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
    gouvernorat: str | None
    developpement_regional: bool | None
    groupe_developpement_regional: int | None = Field(description="1 ou 2 ; vide hors développement régional")
    prix_m2_dt: float | None = Field(description="prix actuel de l'AFI ; vide : l'AFI ne publie pas de prix")
    prix_m2_dernier_publie_dt: float | None = Field(None, description="si pas de prix actuel : dernier prix publié par "
                                                                     "l'AFI, à dire avec sa source et « à confirmer »")
    prix_dernier_publie_source: str | None = None
    prix_dernier_publie_date_source: date | None = None
    prix_m2_subventionne_dt: float | None = Field(None, description="prix au m² après la prime d'infrastructure du "
                                                                    "développement régional, publié sur le site de l'AFI")
    prix_site_afi: float | None = Field(None, description="prix au m² publié sur la page des incitations du site de l'AFI")
    prix_site_afi_date_source: date | None = None
    prix_en_conflit: bool | None = Field(
        None, description="vrai si les sources sont en conflit; nul si la vue ne fournit pas cette comparaison"
    )
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
    z = q("SELECT * FROM v_pub_zones_v2 WHERE zone_id = %s", e.zone_id)
    if not z:
        return None
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
    code = z["gouvernorat_code"]
    gouvernorat = nom_gouvernorat(code)
    prix_actuel = nombre(z.get("prix_m2_dt"))
    dernier_reference = derniers_prix_publies_par_zone().get(str(zid))
    dernier_prix_vue = z.get("prix_m2_dernier_publie_dt")
    if dernier_reference and prix_actuel is None:
        dernier_prix = nombre(dernier_reference["prix_m2_dt"])
        dernier_source = dernier_reference["source"]
        dernier_date = dernier_reference["date_source"]
        if dernier_prix_vue is not None and nombre(dernier_prix_vue) != dernier_prix:
            raise ValueError(f"Divergence de dernier prix publié pour la zone {zid}")
        if z.get("prix_dernier_publie_source") not in (None, dernier_source):
            raise ValueError(f"Divergence de source du dernier prix publié pour la zone {zid}")
        if z.get("prix_dernier_publie_date_source") not in (None, dernier_date):
            raise ValueError(f"Divergence de date du dernier prix publié pour la zone {zid}")
    elif prix_actuel is None and dernier_prix_vue is not None and z.get("prix_dernier_publie_source"):
        dernier_prix = nombre(dernier_prix_vue)
        dernier_source = z["prix_dernier_publie_source"]
        dernier_date = z.get("prix_dernier_publie_date_source")
    else:
        dernier_prix = dernier_source = dernier_date = None

    prix_site_reference = prix_site_afi_par_zone().get(str(zid))
    prix_site = z.get("prix_m2_site_afi_dt")
    prix_subventionne = z.get("prix_m2_subventionne_site_afi_dt")
    prix_site_source = z.get("prix_site_afi_source")
    prix_site_date = z.get("prix_site_afi_date_source")
    if prix_site_reference:
        for valeur_vue, champ in (
            (prix_site, "prix_m2_dt"),
            (prix_subventionne, "prix_m2_subventionne_dt"),
        ):
            valeur_reference = prix_site_reference[champ]
            if valeur_vue is not None and nombre(valeur_vue) != nombre(valeur_reference):
                raise ValueError(f"Divergence de prix du site AFI pour la zone {zid}")
        if prix_site_source not in (None, prix_site_reference["source"]):
            raise ValueError(f"Divergence de source du prix du site AFI pour la zone {zid}")
        if prix_site_date not in (None, prix_site_reference["date_source"]):
            raise ValueError(f"Divergence de date du prix du site AFI pour la zone {zid}")
        prix_site = prix_site_reference["prix_m2_dt"]
        prix_subventionne = prix_site_reference["prix_m2_subventionne_dt"]
        prix_site_source = prix_site_reference["source"]
        prix_site_date = prix_site_reference["date_source"]

    groupe = groupe_developpement_regional(zid, z.get("zone_developpement_regional"))
    groupe_vue = z.get("groupe_developpement_regional")
    if groupe_vue is not None and int(groupe_vue) != groupe:
        raise ValueError(f"Divergence de groupe de développement régional pour la zone {zid}")
    conflit = z.get("prix_en_conflit")
    if conflit is None and prix_actuel is not None and prix_site is not None:
        conflit = prix_actuel != nombre(prix_site)
    sources = [SOURCE_BASE] + [Source(titre=d.titre, url=d.lien) for d in cahiers + plans]
    if dernier_source:
        sources.append(Source(titre=dernier_source, date_source=dernier_date))
    if prix_site_source:
        sources.append(Source(
            titre="Site de l'AFI, incitations en zones de développement régional",
            url=prix_site_source.split(" (")[0],
            date_source=prix_site_date,
        ))
    return FicheZone(zone_id=zid, nom=z["nom_fr"], nom_ar=z["nom_ar"], gouvernorat=gouvernorat,
                     developpement_regional=(
                         bool(z["zone_developpement_regional"])
                         if z.get("zone_developpement_regional") is not None else None
                     ),
                     groupe_developpement_regional=groupe,
                     prix_m2_dt=prix_actuel, prix_m2_dernier_publie_dt=dernier_prix,
                     prix_dernier_publie_source=dernier_source,
                     prix_dernier_publie_date_source=dernier_date,
                     prix_m2_subventionne_dt=nombre(prix_subventionne),
                     prix_site_afi=nombre(prix_site), prix_site_afi_date_source=prix_site_date,
                     prix_en_conflit=bool(conflit) if conflit is not None else None,
                     surface_totale_m2=nombre(z["surface_totale_m2"]),
                     surface_amenagee_m2=nombre(z["surface_amenagee_m2"]),
                     surface_amenagee_calculee_m2=nombre(z.get("surface_amenagee_calculee_m2")),
                     lots_disponibles=z["lots_disponibles"],
                     lots_disponibles_a_confirmer=z["lots_disponibles_a_confirmer"],
                     lots_mis_aux_encheres=z["lots_mis_aux_encheres"], distances=dist, equipements=equip,
                     services_proches=serv, cahiers_des_charges=cahiers, plans_de_lotissement=plans,
                     sources=sources)


class EntreeListeZones(BaseModel):
    gouvernorats: list[int] = Field(default_factory=list, description="codes des gouvernorats (resoudre_lieu)")
    regime: Literal["developpement_regional", "littoral"] | None = None
    groupe_developpement_regional: Literal[1, 2] | None = None
    seulement_avec_lots_disponibles: bool = True


class ResumeZone(BaseModel):
    zone_id: str
    nom: str
    gouvernorat: str | None
    prix_m2_dt: float | None
    lots_disponibles: int
    developpement_regional: bool | None
    groupe_developpement_regional: int | None


class ResultatZones(BaseModel):
    nombre: int
    zones: list[ResumeZone]
    sources: list[Source]


def _resume(r):
    code = r["gouvernorat_code"]
    gouvernorat = nom_gouvernorat(code)
    groupe = groupe_developpement_regional(r["zone_id"], r.get("zone_developpement_regional"))
    groupe_vue = r.get("groupe_developpement_regional")
    if groupe_vue is not None and int(groupe_vue) != groupe:
        raise ValueError(f"Divergence de groupe de développement régional pour la zone {r['zone_id']}")
    return ResumeZone(zone_id=r["zone_id"], nom=r["nom_fr"], gouvernorat=gouvernorat,
                      prix_m2_dt=nombre(r["prix_m2_dt"]), lots_disponibles=r["lots_disponibles"],
                      developpement_regional=(
                          bool(r["zone_developpement_regional"])
                          if r.get("zone_developpement_regional") is not None else None
                      ),
                      groupe_developpement_regional=groupe)


def lister_zones(e: EntreeListeZones) -> ResultatZones:
    sql, p = "SELECT * FROM v_pub_zones_v2 WHERE 1=1", []
    if e.gouvernorats:
        sql += " AND gouvernorat_code IN (" + ",".join(["%s"] * len(e.gouvernorats)) + ")"
        p += e.gouvernorats
    if e.regime:
        sql += " AND zone_developpement_regional = %s"
        p.append(1 if e.regime == "developpement_regional" else 0)
    if e.seulement_avec_lots_disponibles:
        sql += " AND lots_disponibles > 0"
    rows = q(sql + " ORDER BY lots_disponibles DESC, nom_fr", *p)
    if e.groupe_developpement_regional:
        rows = [r for r in rows if groupe_developpement_regional(
            r["zone_id"], r["zone_developpement_regional"]
        ) == e.groupe_developpement_regional]
    return ResultatZones(nombre=len(rows), zones=[_resume(r) for r in rows], sources=[SOURCE_BASE])


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
    rows = q("SELECT z.*, d.nom AS infra, d.km FROM v_pub_zone_distances d JOIN v_pub_zones_v2 z USING (zone_id) "
             "WHERE d.type = %s AND d.km <= %s" + (" AND z.lots_disponibles > 0" if e.seulement_avec_lots_disponibles
                                                     else "") + " ORDER BY d.km", e.type, e.distance_max_km)
    zones = [ZoneProche(**_resume(r).model_dump(), infrastructure=r["infra"], km=nombre(r["km"])) for r in rows]
    return ResultatProximite(nombre=len(zones), zones=zones, sources=[SOURCE_BASE])
