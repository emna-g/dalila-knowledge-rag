"""Préparation d'une demande d'acquisition d'un lot (BF11) : un brouillon à vérifier, jamais déposé par Dalila.

    preremplir(lot_id=None, zone_id=None, session_id=None)  -> ce que Dalila sait déjà (lot, zone, projet de l'étude)
    produire_pdf(demande, lang)                              -> le brouillon en PDF (octets, en mémoire)

Ce qui est prérempli vient de la base de l'AFI (lot, zone, prix : relus ici, jamais pris dans ce que l'interface envoie,
BNF1) et des réponses de l'étude de projet guidée, si le visiteur l'a faite dans cette conversation. Le visiteur
complète et vérifie ; le PDF n'est produit qu'avec sa confirmation (case cochée). Rien n'est envoyé à l'AFI, rien n'est
gardé : le PDF est fait en mémoire et rendu au navigateur ; les coordonnées du demandeur ne sont ni écrites ni
journalisées (BNF8, BNF16). Ce n'est pas le formulaire officiel : le PDF le dit et donne le lieu de dépôt et les pièces
à joindre, d'après les réponses validées de l'AFI (12 à 17).
"""
import datetime as dt
from pydantic import BaseModel, Field
from dalila.traitement.base import nombre, q
from dalila.traitement.etude import POLICES, _lire as lire_session
from dalila.traitement.services import _reponses, _services

# réponses validées de l'AFI : pièces à joindre et étapes, selon le type de zone
PIECES = {True: "kb0014", False: "kb0017"}       # développement régional / littoral et Grand Tunis
CONDITIONS = {True: "kb0013", False: "kb0015"}


class Demandeur(BaseModel):
    nom: str = Field("", max_length=150, description="nom et prénom, ou raison sociale")
    forme_juridique: str = Field("", max_length=80)
    representant: str = Field("", max_length=150)
    telephone: str = Field("", max_length=40)
    courriel: str = Field("", max_length=120)
    adresse: str = Field("", max_length=300)


class Projet(BaseModel):
    activite: str = Field("", max_length=300)
    produits: str = Field("", max_length=300)
    investissement_dt: float | None = Field(None, ge=0, le=1e11)
    emplois: int | None = Field(None, ge=0, le=100000)
    dont_cadres: int | None = Field(None, ge=0, le=100000)
    delai_realisation_mois: int | None = Field(None, ge=0, le=240)
    justification_surface: str = Field("", max_length=1500, description="rapport motivé sur la superficie demandée")


class Demande(BaseModel):
    lot_id: int
    demandeur: Demandeur
    projet: Projet
    confirme: bool = Field(False, description="le visiteur a vérifié le brouillon (obligatoire)")
    lang: str = Field("fr", max_length=10)


# ---------------------------------------------------------------- lot et zone, relus dans la base
def lot_et_zone(lot_id=None, zone_id=None):
    lot = None
    if lot_id is not None:
        r = q("SELECT lot_id, zone_id, lot_num, surface_m2, statut, libelle_carte, a_confirmer, prix_m2_dt, "
              "prix_m2_dernier_publie_dt FROM v_pub_lots WHERE lot_id = %s", lot_id)
        if r:
            r = r[0]
            prix = r["prix_m2_dt"] if r["prix_m2_dt"] is not None else r["prix_m2_dernier_publie_dt"]
            surface = nombre(r["surface_m2"])
            lot = {"lot_id": int(r["lot_id"]), "numero": r["lot_num"], "surface_m2": surface, "statut": r["statut"],
                   "libelle_statut": r["libelle_carte"], "a_confirmer": bool(r["a_confirmer"]),
                   "prix_m2_dt": nombre(prix), "prix_m2_a_confirmer": r["prix_m2_dt"] is None and prix is not None,
                   "prix_terrain_dt": round(surface * float(prix)) if surface and prix is not None else None}
            zone_id = r["zone_id"]
    zone = None
    if zone_id is not None:
        z = q("SELECT zone_id, nom_fr, nom_ar, gouvernorat_fr, gouvernorat_ar, zone_developpement_regional, "
              "groupe_developpement_regional FROM v_pub_zones WHERE zone_id = %s", zone_id)
        if z:
            z = z[0]
            zone = {"zone_id": int(z["zone_id"]), "nom": z["nom_fr"], "nom_ar": z["nom_ar"],
                    "gouvernorat": z["gouvernorat_fr"], "gouvernorat_ar": z["gouvernorat_ar"],
                    "developpement_regional": bool(z["zone_developpement_regional"]),
                    "groupe": z["groupe_developpement_regional"]}
    return lot, zone


def projet_de_l_etude(session_id):
    """Les réponses de l'étude de projet guidée de cette conversation (déjà anonymisées), si elle a été faite."""
    if not session_id:
        return {}
    try:
        slots, _, _ = lire_session(session_id)
    except Exception:  # noqa: BLE001  base injoignable : rien à préremplir
        return {}
    r = {k: v for k, v in (slots.get("reponses") or {}).items()}
    val = lambda k: (r.get(k) or {}).get("valeur")  # noqa: E731
    txt = lambda k: (r.get(k) or {}).get("texte") or ""  # noqa: E731
    p = {"activite": str(val("projet") or txt("projet") or "")[:300], "produits": str(val("produits") or txt("produits") or "")[:300]}
    if isinstance(val("investissement"), (int, float)):
        p["investissement_texte"] = txt("investissement")   # une tranche (« 1 à 15 millions DT ») : à préciser
    if isinstance(val("emplois"), (int, float)):
        p["emplois_texte"] = txt("emplois")
    if txt("surface"):
        p["surface_texte"] = txt("surface")
    return {k: v for k, v in p.items() if v}


def preremplir(lot_id=None, zone_id=None, session_id=None):
    lot, zone = lot_et_zone(lot_id, zone_id)
    dr = bool(zone and zone["developpement_regional"])
    reponses = _reponses([PIECES[dr], CONDITIONS[dr]]) if zone else []
    return {
        "lot": lot, "zone": zone, "projet": projet_de_l_etude(session_id),
        "lot_disponible": bool(lot and lot["statut"] == "disponible"),
        "lieu_depot": _services()["acquisition"]["lieu_depot"],
        "pieces": [{"id": r.id, "titre": r.question, "texte": r.texte} for r in reponses],
        "formulaire_officiel": "https://www.afi.nat.tn/fr/nos-services/",
    }


# ---------------------------------------------------------------- le brouillon en PDF
T = {
    "fr": {"titre": "Demande d'acquisition d'un lot industriel", "brouillon": "BROUILLON préparé avec Dalila, à vérifier",
           "avert": "Ce document n'est pas le formulaire officiel et n'a pas été déposé : Dalila ne transmet rien à l'AFI. "
                    "Reportez ces informations sur le formulaire de l'AFI (bureau d'accueil, site afi.nat.tn ou formulaire "
                    "en ligne), joignez les pièces ci-dessous et déposez le dossier vous-même.",
           "demandeur": "1. Demandeur", "lot": "2. Lot demandé", "projet": "3. Projet", "depot": "4. Où déposer",
           "pieces": "5. Pièces à joindre (réponse validée de l'AFI)", "prix_note": "Prix au m² publié par l'AFI ; "
           "frais de rédaction du contrat et de délimitation non publiés par l'AFI.",
           "nom": "Nom et prénom / raison sociale", "forme": "Forme juridique", "rep": "Représentant légal",
           "tel": "Téléphone", "mail": "Courriel", "adr": "Adresse", "zone": "Zone industrielle", "gouv": "Gouvernorat",
           "num": "Lot n°", "surf": "Surface", "prix": "Prix au m²", "total": "Prix du terrain", "etat": "État du lot",
           "dr": "Zone de développement régional", "act": "Activité", "prod": "Produits ou services",
           "inv": "Investissement prévu", "empl": "Emplois prévus", "cadres": "dont cadres",
           "delai": "Délai de réalisation", "mois": "mois", "just": "Justification de la surface demandée",
           "non_dispo": "ATTENTION : ce lot n'est pas indiqué disponible dans la base de l'AFI ; l'attribution dépend de "
                        "la disponibilité des terrains.", "a_conf": "à confirmer auprès de l'AFI", "oui": "oui",
           "signature": "Date et signature du demandeur :", "vide": "à compléter"},
    "en": {"titre": "Application to acquire an industrial lot", "brouillon": "DRAFT prepared with Dalila, to be checked",
           "avert": "This document is not the official form and has not been submitted: Dalila sends nothing to AFI. "
                    "Copy this information onto AFI's form (reception desk, afi.nat.tn or online form), attach the "
                    "documents below and submit the file yourself.",
           "demandeur": "1. Applicant", "lot": "2. Requested lot", "projet": "3. Project", "depot": "4. Where to submit",
           "pieces": "5. Documents to attach (AFI validated answer)", "prix_note": "Price per m² published by AFI; "
           "contract drafting and boundary survey fees are not published by AFI.",
           "nom": "Full name / company name", "forme": "Legal form", "rep": "Legal representative", "tel": "Phone",
           "mail": "Email", "adr": "Address", "zone": "Industrial zone", "gouv": "Governorate", "num": "Lot no.",
           "surf": "Area", "prix": "Price per m²", "total": "Land price", "etat": "Lot status",
           "dr": "Regional development zone", "act": "Activity", "prod": "Products or services",
           "inv": "Planned investment", "empl": "Planned jobs", "cadres": "of which managers",
           "delai": "Completion time", "mois": "months", "just": "Justification of the requested area",
           "non_dispo": "WARNING: this lot is not shown as available in AFI's database; allocation depends on land "
                        "availability.", "a_conf": "to be confirmed with AFI", "oui": "yes",
           "signature": "Date and applicant's signature:", "vide": "to be completed"},
    "ar": {"titre": "مطلب اقتناء مقسم صناعي", "brouillon": "مسودة أُعدّت مع دليلة، يجب التثبت منها",
           "avert": "هذه الوثيقة ليست المطلب الرسمي ولم يتم إيداعها: دليلة لا ترسل أي شيء إلى الوكالة. "
                    "انقل هذه المعطيات إلى مطلب الوكالة (مكتب الاستقبال، موقع afi.nat.tn أو المطلب الإلكتروني)، "
                    "وأرفق الوثائق أدناه، وأودع الملف بنفسك.",
           "demandeur": "1. صاحب المطلب", "lot": "2. المقسم المطلوب", "projet": "3. المشروع", "depot": "4. مكان الإيداع",
           "pieces": "5. الوثائق المطلوبة (إجابة مصادق عليها من الوكالة)", "prix_note": "سعر المتر المربع المنشور من "
           "الوكالة؛ معاليم تحرير العقد والتحديد غير منشورة.",
           "nom": "الاسم واللقب / الاسم التجاري", "forme": "الشكل القانوني", "rep": "الممثل القانوني", "tel": "الهاتف",
           "mail": "البريد الإلكتروني", "adr": "العنوان", "zone": "المنطقة الصناعية", "gouv": "الولاية", "num": "رقم المقسم",
           "surf": "المساحة", "prix": "سعر المتر المربع", "total": "ثمن الأرض", "etat": "حالة المقسم",
           "dr": "منطقة تنمية جهوية", "act": "النشاط", "prod": "المنتجات أو الخدمات", "inv": "الاستثمار المتوقع",
           "empl": "مواطن الشغل المتوقعة", "cadres": "منها إطارات", "delai": "مدة الإنجاز", "mois": "شهر",
           "just": "تبرير المساحة المطلوبة",
           "non_dispo": "تنبيه: هذا المقسم غير مبين كمتاح في قاعدة بيانات الوكالة؛ الإسناد رهين توفر الأراضي.",
           "a_conf": "يجب التثبت منه لدى الوكالة", "oui": "نعم", "signature": "التاريخ وإمضاء صاحب المطلب:",
           "vide": "يُستكمل"},
}


ETATS = {"disponible": ("Disponible", "Available", "متاح"), "reserve": ("Réservé", "Reserved", "محجوز"),
         "mis_aux_encheres": ("Aux enchères", "At auction", "للبتة"), "attribue": ("Attribué", "Allocated", "مسند"),
         "non_disponible": ("Non disponible", "Not available", "غير متاح"), "sans_statut": ("Non renseigné", "Unknown", "غير محدد")}
GROUPE = {"fr": "groupe", "en": "group", "ar": "المجموعة"}
DEPOT_AR = "kb0092"   # réponse validée de l'AFI, en arabe : où déposer la demande


def _n(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ") if x is not None else None


def produire_pdf(d: Demande) -> bytes:
    from fpdf import FPDF
    lang = d.lang if d.lang in T else ("ar" if d.lang in ("aeb", "tn") else "fr")
    t = T[lang]
    pre = preremplir(lot_id=d.lot_id)
    lot, zone = pre["lot"], pre["zone"]
    if not lot:
        raise ValueError("lot inconnu")
    pdf = FPDF()
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    pdf.add_font("Noto", "", str(POLICES / "NotoSans.ttf"))
    pdf.add_font("NotoAr", "", str(POLICES / "NotoNaskhArabic.ttf"))
    pdf.set_fallback_fonts(["NotoAr"])
    pdf.set_text_shaping(True)
    aligne = "R" if lang == "ar" else "L"

    def texte(x, taille=10, couleur=(30, 35, 48), h=6):
        pdf.set_font("Noto", size=taille)
        pdf.set_text_color(*couleur)
        pdf.multi_cell(0, h, str(x), align=aligne, new_x="LMARGIN", new_y="NEXT")

    def titre(x):
        pdf.ln(3)
        texte(x, 12, (10, 111, 169), 8)

    def champ(libelle, valeur):
        v = str(valeur).strip() if valeur not in (None, "") else f"…………… ({t['vide']})"
        texte(f"{libelle} : {v}")

    texte(f"AFI · {t['titre']}", 17, (23, 89, 139), 9)
    texte(f"{t['brouillon']} · {dt.date.today().isoformat()}", 9, (233, 78, 27))
    pdf.ln(1)
    texte(t["avert"], 8.5, (74, 85, 96), 5)

    titre(t["demandeur"])
    D = d.demandeur
    for k, v in (("nom", D.nom), ("forme", D.forme_juridique), ("rep", D.representant), ("tel", D.telephone),
                 ("mail", D.courriel), ("adr", D.adresse)):
        champ(t[k], v)

    titre(t["lot"])
    nom_zone = (zone["nom_ar"] or zone["nom"]) if lang == "ar" and zone else (zone["nom"] if zone else "")
    gouv = (zone["gouvernorat_ar"] or zone["gouvernorat"]) if lang == "ar" and zone else (zone["gouvernorat"] if zone else "")
    champ(t["zone"], nom_zone)
    champ(t["gouv"], gouv)
    champ(t["num"], lot["numero"])
    champ(t["surf"], f"{_n(lot['surface_m2'])} m²" if lot["surface_m2"] else None)
    if lot["prix_m2_dt"] is not None:
        champ(t["prix"], f"{_n(lot['prix_m2_dt'], 0 if float(lot['prix_m2_dt']).is_integer() else 1)} DT"
              + (f" ({t['a_conf']})" if lot["prix_m2_a_confirmer"] else ""))
    if lot["prix_terrain_dt"] is not None:
        champ(t["total"], f"{_n(lot['surface_m2'])} m² × {_n(lot['prix_m2_dt'], 0 if float(lot['prix_m2_dt']).is_integer() else 1)} DT = {_n(lot['prix_terrain_dt'])} DT")
    etat = ETATS.get(lot["statut"], (lot["libelle_statut"],) * 3)[("fr", "en", "ar").index(lang)]
    champ(t["etat"], etat + (f" ({t['a_conf']})" if lot["a_confirmer"] else ""))
    if zone and zone["developpement_regional"]:
        champ(t["dr"], t["oui"] + (f" ({GROUPE[lang]} {zone['groupe']})" if zone.get("groupe") else ""))
    texte(t["prix_note"], 8, (74, 85, 96), 5)
    if lot["statut"] != "disponible":
        texte(t["non_dispo"], 9, (233, 78, 27))

    titre(t["projet"])
    P = d.projet
    champ(t["act"], P.activite)
    champ(t["prod"], P.produits)
    champ(t["inv"], f"{_n(P.investissement_dt)} DT" if P.investissement_dt is not None else None)
    champ(t["empl"], (f"{P.emplois}" + (f" ({t['cadres']} {P.dont_cadres})" if P.dont_cadres is not None else ""))
          if P.emplois is not None else None)
    champ(t["delai"], f"{P.delai_realisation_mois} {t['mois']}" if P.delai_realisation_mois is not None else None)
    champ(t["just"], P.justification_surface)

    titre(t["depot"])
    depot_ar = _reponses([DEPOT_AR]) if lang == "ar" else []
    texte(depot_ar[0].texte.split(chr(10), 1)[-1].strip() if depot_ar else pre["lieu_depot"], 9.5)
    titre(t["pieces"])
    for p in pre["pieces"][:1]:
        texte(p["texte"], 9, h=5)
    texte(pre["formulaire_officiel"], 8.5, (10, 111, 169), 5)

    pdf.ln(8)
    texte(t["signature"], 10)
    return bytes(pdf.output())
