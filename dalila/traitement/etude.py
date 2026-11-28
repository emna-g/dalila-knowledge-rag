"""Étude de projet guidée (cahier des charges : BF4, cas d'utilisation 7) : un entretien de 10 questions, puis l'étude
en PDF.

    commencer(session_id, lang)        -> {"message": première question avec [[CHOIX:…]], "fin": False}
    repondre(session_id, texte)        -> question suivante, ou {"message": résumé + [[PDF:…]], "fin": True}
    en_cours(session_id)               -> True si une étude attend une réponse

L'entretien est mené par le code, sans modèle de langue : chaque question arrive aussitôt, dans la langue du visiteur
(fr, en, ar, de, tr ; les dialectes en lettres arabes reçoivent l'arabe, en arabizi le français). Les boutons de choix
évitent d'avoir à lire des montants écrits librement ; une réponse écrite est acceptée aussi. L'état est gardé dans
agent_sessions. À la fin, le guide du projet (outil conseiller : activité, organisme, zones, incitations, démarche) est
mis en page en PDF : rien n'y est estimé, chaque chiffre vient de la base de l'AFI ou d'un texte cité.
"""
import datetime as dt, json, re, secrets
from dalila.config import DONNEES, RACINE, db

DOSSIER = DONNEES / "etudes"
POLICES = RACINE / "dalila" / "traitement" / "polices"

# (clé, type, {langue: question}, {langue: [(libellé, valeur)]})
QUESTIONS = [
    ("projet", "texte", {"fr": "Quelle activité voulez-vous lancer ? (par exemple : transformation d'huile d'olive)",
                         "en": "What activity do you want to start? (for example: olive oil processing)",
                         "ar": "ما هو النشاط الذي تريد إطلاقه؟ (مثلا: تحويل زيت الزيتون)",
                         "de": "Welche Tätigkeit möchten Sie aufnehmen? (zum Beispiel: Olivenölverarbeitung)",
                         "tr": "Hangi faaliyeti başlatmak istiyorsunuz? (örneğin: zeytinyağı işleme)"}, {}),
    ("produits", "texte", {"fr": "Quels produits ou services allez-vous fabriquer ou proposer ?",
                           "en": "What products or services will you make or offer?",
                           "ar": "ما هي المنتجات أو الخدمات التي ستصنعها أو تقدمها؟",
                           "de": "Welche Produkte oder Dienstleistungen werden Sie herstellen oder anbieten?",
                           "tr": "Hangi ürünleri veya hizmetleri üreteceksiniz ya da sunacaksınız?"}, {}),
    ("lieu", "lieu", {"fr": "Dans quel gouvernorat ou quelle région voulez-vous vous installer ?",
                      "en": "In which governorate or region do you want to settle?",
                      "ar": "في أي ولاية أو جهة تريد أن تستقر؟",
                      "de": "In welchem Gouvernorat oder welcher Region möchten Sie sich ansiedeln?",
                      "tr": "Hangi vilayette veya bölgede yerleşmek istiyorsunuz?"},
     {"fr": [("Pas de préférence", None)], "en": [("No preference", None)], "ar": [("لا تفضيل", None)],
      "de": [("Keine Vorliebe", None)], "tr": [("Tercihim yok", None)]}),
    ("surface", "nombre", {"fr": "De quelle surface de terrain avez-vous besoin ?",
                           "en": "How much land do you need?", "ar": "ما هي مساحة الأرض التي تحتاجها؟",
                           "de": "Wie viel Grundstücksfläche benötigen Sie?", "tr": "Ne kadar araziye ihtiyacınız var?"},
     {"fr": [("Moins de 1 000 m²", 500), ("1 000 à 3 000 m²", 1000), ("3 000 à 10 000 m²", 3000), ("Plus de 10 000 m²", 10000)],
      "en": [("Less than 1,000 m²", 500), ("1,000 to 3,000 m²", 1000), ("3,000 to 10,000 m²", 3000), ("More than 10,000 m²", 10000)],
      "ar": [("أقل من 1000 م²", 500), ("من 1000 إلى 3000 م²", 1000), ("من 3000 إلى 10000 م²", 3000), ("أكثر من 10000 م²", 10000)],
      "de": [("Weniger als 1.000 m²", 500), ("1.000 bis 3.000 m²", 1000), ("3.000 bis 10.000 m²", 3000), ("Mehr als 10.000 m²", 10000)],
      "tr": [("1.000 m²'den az", 500), ("1.000 ile 3.000 m²", 1000), ("3.000 ile 10.000 m²", 3000), ("10.000 m²'den fazla", 10000)]}),
    ("investissement", "nombre", {"fr": "Quel est le coût d'investissement prévu ?", "en": "What is the planned investment cost?",
                                  "ar": "ما هي الكلفة المتوقعة للاستثمار؟", "de": "Wie hoch sind die geplanten Investitionskosten?",
                                  "tr": "Planlanan yatırım maliyeti nedir?"},
     {"fr": [("Moins de 1 million DT", 500000), ("1 à 15 millions DT", 5000000), ("15 millions DT ou plus", 15000000)],
      "en": [("Less than 1 million DT", 500000), ("1 to 15 million DT", 5000000), ("15 million DT or more", 15000000)],
      "ar": [("أقل من مليون دينار", 500000), ("من 1 إلى 15 مليون دينار", 5000000), ("15 مليون دينار أو أكثر", 15000000)],
      "de": [("Weniger als 1 Million DT", 500000), ("1 bis 15 Millionen DT", 5000000), ("15 Millionen DT oder mehr", 15000000)],
      "tr": [("1 milyon DT'den az", 500000), ("1 ile 15 milyon DT", 5000000), ("15 milyon DT veya fazlası", 15000000)]}),
    ("emplois", "nombre", {"fr": "Combien d'emplois prévoyez-vous ?", "en": "How many jobs do you plan to create?",
                           "ar": "كم عدد مواطن الشغل المتوقعة؟", "de": "Wie viele Arbeitsplätze planen Sie?",
                           "tr": "Kaç kişilik istihdam planlıyorsunuz?"},
     {"fr": [("1 à 10", 1), ("11 à 50", 11), ("51 à 200", 51), ("Plus de 200", 201)],
      "en": [("1 to 10", 1), ("11 to 50", 11), ("51 to 200", 51), ("More than 200", 201)],
      "ar": [("من 1 إلى 10", 1), ("من 11 إلى 50", 11), ("من 51 إلى 200", 51), ("أكثر من 200", 201)],
      "de": [("1 bis 10", 1), ("11 bis 50", 11), ("51 bis 200", 51), ("Mehr als 200", 201)],
      "tr": [("1 ile 10", 1), ("11 ile 50", 11), ("51 ile 200", 51), ("200'den fazla", 201)]}),
    ("export", "choix", {"fr": "Votre production sera-t-elle exportée ?", "en": "Will your production be exported?",
                         "ar": "هل سيتم تصدير إنتاجك؟", "de": "Wird Ihre Produktion exportiert?", "tr": "Üretiminiz ihraç edilecek mi?"},
     {"fr": [("Oui, totalement", "totalement"), ("En partie", "en partie"), ("Non", "non")],
      "en": [("Yes, fully", "totalement"), ("Partly", "en partie"), ("No", "non")],
      "ar": [("نعم، كليا", "totalement"), ("جزئيا", "en partie"), ("لا", "non")],
      "de": [("Ja, vollständig", "totalement"), ("Teilweise", "en partie"), ("Nein", "non")],
      "tr": [("Evet, tamamen", "totalement"), ("Kısmen", "en partie"), ("Hayır", "non")]}),
    ("infrastructure", "choix", {"fr": "Avez-vous besoin d'être proche d'une infrastructure ?",
                                 "en": "Do you need to be close to an infrastructure?", "ar": "هل تحتاج أن تكون قريبا من بنية تحتية؟",
                                 "de": "Müssen Sie in der Nähe einer Infrastruktur sein?", "tr": "Bir altyapıya yakın olmanız gerekiyor mu?"},
     {"fr": [("Port", "port"), ("Aéroport", "aeroport"), ("Autoroute", "autoroute"), ("Gare", "gare"), ("Aucune", None)],
      "en": [("Port", "port"), ("Airport", "aeroport"), ("Motorway", "autoroute"), ("Railway station", "gare"), ("None", None)],
      "ar": [("ميناء", "port"), ("مطار", "aeroport"), ("طريق سيارة", "autoroute"), ("محطة قطار", "gare"), ("لا شيء", None)],
      "de": [("Hafen", "port"), ("Flughafen", "aeroport"), ("Autobahn", "autoroute"), ("Bahnhof", "gare"), ("Keine", None)],
      "tr": [("Liman", "port"), ("Havalimanı", "aeroport"), ("Otoyol", "autoroute"), ("Tren istasyonu", "gare"), ("Hiçbiri", None)]}),
    ("besoins", "texte", {"fr": "Quels besoins particuliers en eau, électricité ou gaz ?",
                          "en": "Any particular needs for water, electricity or gas?", "ar": "ما هي حاجياتك الخاصة من الماء أو الكهرباء أو الغاز؟",
                          "de": "Besondere Anforderungen an Wasser, Strom oder Gas?", "tr": "Su, elektrik veya gaz için özel ihtiyaçlarınız var mı?"},
     {"fr": [("Rien de particulier", "rien de particulier")], "en": [("Nothing special", "rien de particulier")],
      "ar": [("لا شيء خاص", "rien de particulier")], "de": [("Nichts Besonderes", "rien de particulier")],
      "tr": [("Özel bir şey yok", "rien de particulier")]}),
    ("calendrier", "choix", {"fr": "Quand voulez-vous démarrer ?", "en": "When do you want to start?", "ar": "متى تريد أن تبدأ؟",
                             "de": "Wann möchten Sie beginnen?", "tr": "Ne zaman başlamak istiyorsunuz?"},
     {"fr": [("Dans moins de 6 mois", "moins de 6 mois"), ("Dans 6 à 12 mois", "6 à 12 mois"), ("Dans plus d'un an", "plus d'un an")],
      "en": [("Within 6 months", "moins de 6 mois"), ("In 6 to 12 months", "6 à 12 mois"), ("In more than a year", "plus d'un an")],
      "ar": [("خلال أقل من 6 أشهر", "moins de 6 mois"), ("خلال 6 إلى 12 شهرا", "6 à 12 mois"), ("بعد أكثر من سنة", "plus d'un an")],
      "de": [("In weniger als 6 Monaten", "moins de 6 mois"), ("In 6 bis 12 Monaten", "6 à 12 mois"), ("In mehr als einem Jahr", "plus d'un an")],
      "tr": [("6 aydan kısa sürede", "moins de 6 mois"), ("6 ile 12 ay içinde", "6 à 12 mois"), ("Bir yıldan fazla", "plus d'un an")]}),
]
ARRET = {"fr": "Arrêter l'étude", "en": "Stop the study", "ar": "إيقاف الدراسة", "de": "Studie abbrechen", "tr": "Çalışmayı durdur"}
TEXTES = {
    "debut": {"fr": "Je vous pose 10 questions, puis je prépare votre étude de projet en PDF.",
              "en": "I will ask you 10 questions, then prepare your project study as a PDF.",
              "ar": "سأطرح عليك 10 أسئلة، ثم أعدّ دراسة مشروعك في ملف PDF.",
              "de": "Ich stelle Ihnen 10 Fragen und erstelle dann Ihre Projektstudie als PDF.",
              "tr": "Size 10 soru soracağım, ardından proje çalışmanızı PDF olarak hazırlayacağım."},
    "fin": {"fr": "Votre étude de projet est prête.", "en": "Your project study is ready.", "ar": "دراسة مشروعك جاهزة.",
            "de": "Ihre Projektstudie ist fertig.", "tr": "Proje çalışmanız hazır."},
    "arret": {"fr": "Étude arrêtée. Vous pouvez poser une autre question.", "en": "Study stopped. You can ask another question.",
              "ar": "تم إيقاف الدراسة. يمكنك طرح سؤال آخر.", "de": "Studie abgebrochen. Sie können eine andere Frage stellen.",
              "tr": "Çalışma durduruldu. Başka bir soru sorabilirsiniz."},
    "titre": {"fr": "Étude de projet", "en": "Project study", "ar": "دراسة مشروع", "de": "Projektstudie", "tr": "Proje çalışması"},
}
TITRES_PDF = {  # sections du PDF
    "fr": ["Votre projet", "Activité et organisme compétent", "Zones proposées", "Incitations", "Démarche d'acquisition", "Sources"],
    "en": ["Your project", "Activity and competent body", "Proposed zones", "Incentives", "Acquisition procedure", "Sources"],
    "ar": ["مشروعك", "النشاط والهيكل المختص", "المناطق المقترحة", "الحوافز", "إجراءات الاقتناء", "المصادر"],
    "de": ["Ihr Projekt", "Tätigkeit und zuständige Stelle", "Vorgeschlagene Zonen", "Förderungen", "Erwerbsverfahren", "Quellen"],
    "tr": ["Projeniz", "Faaliyet ve yetkili kurum", "Önerilen bölgeler", "Teşvikler", "Edinim süreci", "Kaynaklar"],
}
AVERTISSEMENT = {"fr": "Chiffres tirés de la base de l'AFI et des textes cités ; à confirmer auprès de l'AFI (+216 71 124 260).",
                 "en": "Figures from the AFI database and cited texts; to be confirmed with AFI (+216 71 124 260).",
                 "ar": "الأرقام مأخوذة من قاعدة بيانات الوكالة والنصوص المذكورة؛ يجب التأكد منها لدى الوكالة (+216 71 124 260).",
                 "de": "Zahlen aus der AFI-Datenbank und den zitierten Texten; bei der AFI zu bestätigen (+216 71 124 260).",
                 "tr": "Rakamlar AFI veritabanından ve alıntılanan metinlerden alınmıştır; AFI ile teyit edilmelidir (+216 71 124 260)."}
DIALECTES = {"aeb", "tn"}


def langue_etude(lang, texte=""):
    """Langue des questions : fr, en, ar, de, tr ; un dialecte en lettres arabes reçoit l'arabe, en arabizi le français."""
    code = (lang or "fr").lower()
    if code in DIALECTES:
        return "ar" if sum("؀" <= c <= "ۿ" for c in texte) > len(texte) / 3 else "fr"
    return code[:2] if code[:2] in TEXTES["fin"] else "fr"


# ---------------------------------------------------------------- état (agent_sessions)
def _lire(session_id):
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute("SELECT slots, state, lang FROM agent_sessions WHERE session_id = %s", (session_id,))
            r = cur.fetchone()
    finally:
        con.close()
    return (json.loads(r["slots"] or "{}"), r["state"], r["lang"]) if r else ({}, None, None)


def _ecrire(session_id, slots, state, lang):
    con = db("rw")
    try:
        with con.cursor() as cur:
            cur.execute("INSERT INTO agent_sessions (session_id, lang, slots, state) VALUES (%s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE lang = VALUES(lang), slots = VALUES(slots), state = VALUES(state)",
                        (session_id, lang, json.dumps(slots, ensure_ascii=False), state))
    finally:
        con.close()


def en_cours(session_id):
    return bool(session_id) and _lire(session_id)[1] == "etude"


def _question(i, lang):
    cle, _, textes, choix = QUESTIONS[i]
    boutons = [lib for lib, _ in choix.get(lang, choix.get("fr", []))] + [ARRET[lang]]
    return f"{i + 1}/10 · {textes[lang]}\n" + " ".join(f"[[CHOIX:{b}]]" for b in boutons)


def commencer(session_id, lang="fr", texte=""):
    l = langue_etude(lang, texte)
    _ecrire(session_id, {"etape": 0, "reponses": {}}, "etude", l)
    return {"message": TEXTES["debut"][l] + "\n\n" + _question(0, l), "fin": False}


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def _valeur(i, texte, lang):
    """Réponse du visiteur -> (valeur, texte gardé). Bouton : sa valeur ; nombre écrit : ce nombre ; sinon le texte."""
    cle, typ, _, choix = QUESTIONS[i]
    for lib, val in choix.get(lang, []) + choix.get("fr", []):
        if _norm(lib) == _norm(texte):
            return val, lib
    if typ == "nombre":
        m = re.search(r"\d[\d\s.,]*", texte)
        if m:
            chiffres = re.sub(r"[\s.,](?=\d{3}\b)", "", m.group()).replace(",", ".")
            try:
                return float(chiffres), texte.strip()
            except ValueError:
                pass
    if typ == "choix":
        return None, texte.strip()
    return texte.strip() or None, texte.strip()


def repondre(session_id, texte):
    from dalila.harnais.garde_fous import anonymiser
    slots, _, lang = _lire(session_id)
    lang = lang or "fr"
    if _norm(texte) in {_norm(a) for a in ARRET.values()}:
        _ecrire(session_id, {}, None, lang)
        return {"message": TEXTES["arret"][lang], "fin": True}
    i = slots.get("etape", 0)
    valeur, lu = _valeur(i, anonymiser(texte)[:300], lang)
    slots["reponses"][QUESTIONS[i][0]] = {"valeur": valeur, "texte": lu}
    slots["etape"] = i + 1
    if i + 1 < len(QUESTIONS):
        _ecrire(session_id, slots, "etude", lang)
        return {"message": _question(i + 1, lang), "fin": False}
    _ecrire(session_id, slots, "etude_finie", lang)
    jeton, guide = produire_pdf(slots["reponses"], lang)
    zones = "\n".join(f"- [[ZONE:{z['zone_id']}:{z['nom']}]] {z['gouvernorat']} · {z['lots_adaptes']} lots"
                      for z in guide.get("zones", []))
    return {"message": f"{TEXTES['fin'][lang]}\n\n{zones}\n[[PDF:/carte/etude/{jeton}.pdf:{TEXTES['titre'][lang]}]]".strip(),
            "fin": True, "pdf": f"/carte/etude/{jeton}.pdf"}


# ---------------------------------------------------------------- étude : guide + PDF
def guide_du_projet(reponses):
    from dalila.traitement.registre import appeler
    v = {k: r.get("valeur") for k, r in reponses.items()}
    args = {"secteur": str(v.get("projet") or v.get("produits") or "projet industriel")[:200]}  # l'activité seule
    if v.get("lieu"):
        args["lieu"] = str(v["lieu"])[:100]
    for cle, champ in (("surface", "surface_m2"), ("investissement", "investissement_dt"), ("emplois", "emplois")):
        if isinstance(v.get(cle), (int, float)) and v[cle] > 0:
            args[champ] = int(v[cle]) if champ == "emplois" else float(v[cle])
    if v.get("infrastructure") in ("port", "aeroport", "autoroute", "gare"):
        args["proche_de"] = v["infrastructure"]
    g = appeler("conseiller", args)
    if g.get("lieux_a_proposer") and "lieu" in args:  # lieu ambigu (« Tunis ») : l'étude se fait sans lui
        args.pop("lieu")
        g = appeler("conseiller", args)
    return g


def produire_pdf(reponses, lang="fr"):
    from fpdf import FPDF
    g = guide_du_projet(reponses)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    jeton = secrets.token_hex(12)
    t = TITRES_PDF[lang]
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Noto", "", str(POLICES / "NotoSans.ttf"))
    pdf.add_font("NotoAr", "", str(POLICES / "NotoNaskhArabic.ttf"))
    pdf.set_fallback_fonts(["NotoAr"])
    pdf.set_text_shaping(True)
    aligne = "R" if lang == "ar" else "L"

    def titre(x, taille=13):
        pdf.ln(3)
        pdf.set_font("Noto", size=taille)
        pdf.set_text_color(10, 111, 169)
        pdf.multi_cell(0, 8, x, align=aligne, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 35, 48)
        pdf.set_font("Noto", size=10)

    def ligne(x):
        x = chr(10).join(l.lstrip("#").strip() for l in str(x).splitlines())  # titres markdown des pages lues
        pdf.multi_cell(0, 6, x, align=aligne, new_x="LMARGIN", new_y="NEXT")

    def coupe(x, n):
        """Au plus n caractères, coupés à la fin d'une ligne ou d'un mot."""
        if len(x) <= n:
            return x
        x = x[:n]
        return (x.rsplit(chr(10), 1)[0] if chr(10) in x[n // 2:] else x.rsplit(" ", 1)[0]) + " …"

    titre(f"AFI · Dalila · {TEXTES['titre'][lang]}", 18)
    ligne(dt.date.today().isoformat())
    titre(t[0])
    for cle, _, textes, _ in QUESTIONS:
        r = reponses.get(cle, {})
        if r.get("texte"):
            ligne(f"• {textes[lang].split('?')[0].split('؟')[0]} : {r['texte']}")
    titre(t[1])
    if g.get("activites"):
        ligne(f"• {g['activites'][0]['libelle']} ({', '.join(g.get('secteurs', []))})")
    noms = {o["id"]: o["nom"] for o in g.get("organismes", [])}
    for o in g.get("organisme_competent", []):
        ligne(f"• {noms.get(o, o)} ({o})")
    if g.get("raison_organisme"):
        ligne(g["raison_organisme"])
    titre(t[2])
    for z in g.get("zones", []):
        prix = f" · {z['prix_m2_dt']:g} DT/m²" if z.get("prix_m2_dt") is not None else ""
        sub = f" (subventionné : {z['prix_m2_subventionne_dt']:g} DT/m²)" if z.get("prix_m2_subventionne_dt") else ""
        dr = " · développement régional" if z.get("developpement_regional") else ""
        km = f" · {z['km']:g} km" if z.get("km") is not None else ""
        ligne(f"• {z['nom']} ({z['gouvernorat']}) : {z['lots_adaptes']} lots{prix}{sub}{dr}{km}")
        if z.get("cahier_des_charges"):
            ligne(f"   {z['cahier_des_charges']}")
    if g.get("note"):
        ligne(g["note"])
    titre(t[3])
    for i in g.get("incitations", [])[:3]:
        ligne(f"• {i.get('titre') or ''}")
        if i.get("extrait"):
            ligne(coupe(i["extrait"], 300))
    titre(t[4])
    if g.get("demarche_lieu_depot"):
        ligne(f"• {g['demarche_lieu_depot']}")
    if g.get("demarche_criteres"):
        ligne(coupe(g["demarche_criteres"], 600))
    titre(t[5])
    vues = set()
    for s in g.get("sources", []):
        cle = (s.get("titre"), s.get("url"))
        if cle not in vues:  # une source citée une fois
            vues.add(cle)
            ligne(f"• {s.get('titre')}" + (f" : {s['url']}" if s.get("url") else ""))
    pdf.ln(4)
    pdf.set_font("Noto", size=8)
    ligne(AVERTISSEMENT[lang])
    pdf.output(str(DOSSIER / f"{jeton}.pdf"))
    return jeton, g


def chemin_pdf(jeton):
    if not re.fullmatch(r"[0-9a-f]{24}", jeton or ""):
        return None
    p = DOSSIER / f"{jeton}.pdf"
    return p if p.exists() else None
