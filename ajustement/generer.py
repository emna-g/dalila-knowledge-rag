"""Jeu d'ajustement de l'agent (Qwen3-4B-Instruct) : conversations complètes, exactes par construction.

    .venv\\Scripts\\python -m ajustement.generer              questions, appels d'outils et réponses à modèles
    .venv\\Scripts\\python -m ajustement.generer --enseignant  + réponses écrites par le modèle local (démarches,
                                                             passages), gardées seulement si elles passent les contrôles

Chaque exemple est une conversation telle que l'agent la vit en service : consignes et outils de production, question
du visiteur, appel d'outil, VRAI résultat de l'outil (base MariaDB, vue courte du harnais), rappel de langue du
harnais, réponse courte. L'appel d'outil attendu est connu par construction (la question est écrite à partir de lui)
et vérifié en l'exécutant. Les réponses à modèles sont remplies avec les nombres du résultat ; toutes passent la
vérification d'ancrage. Les 57 vraies questions (eval/testset) ne servent jamais ici : elles restent le jeu de test.

Langues : français, anglais, arabe, allemand, turc, tunisien (lettres arabes et latines) ; l'algérien et le libyen ne
sont plus proposés (2026-11-28 ; le modèle ajusté actuel en a encore vu quelques exemples). Sortie : donnees/ajustement/{train,val}.jsonl et outils.json.
"""
import argparse, csv, json, random, re
from dalila.config import DONNEES, RACINE
from dalila.harnais.agent import CONSIGNE_HORS_SUJET, Agent, appeler_avec_lieu, degenere
from dalila.harnais.consignes import RAPPEL_LANGUE, systeme
from dalila.harnais.garde_fous import verifier_ancrage
from dalila.harnais.vues import _n, vue
from dalila.traitement.base import q

SORTIE = DONNEES / "ajustement"
ARABE = {"ar", "aeb_ar"}
LANGUES = ["fr", "en", "ar", "de", "tr", "aeb_ar", "aeb_lat"]
CODE = {"fr": "fr", "en": "en", "ar": "ar", "de": "de", "tr": "tr", "aeb_ar": "aeb", "aeb_lat": "aeb"}  # code envoyé par l'interface (champ lang)

# ------------------------------------------------------------------ lots
FILTRES = {  # (champ, valeur) -> morceau de phrase
    "fr": {"surface_min_m2": " de {v} m² minimum", "budget_max_dt": " avec un budget de {v} DT", "prix_max_m2_dt": " à moins de {v} DT le m²"},
    "en": {"surface_min_m2": " of at least {v} m²", "budget_max_dt": " with a budget of {v} DT", "prix_max_m2_dt": " under {v} DT per m²"},
    "de": {"surface_min_m2": " mit mindestens {v} m²", "budget_max_dt": " mit einem Budget von {v} DT", "prix_max_m2_dt": " unter {v} DT pro m²"},
    "tr": {"surface_min_m2": " en az {v} m²", "budget_max_dt": " {v} DT bütçeyle", "prix_max_m2_dt": " m² fiyatı {v} DT altında"},
    "ar": {"surface_min_m2": " بمساحة {v} م² على الأقل", "budget_max_dt": " بميزانية {v} دينار", "prix_max_m2_dt": " بأقل من {v} دينار للمتر المربع"},
    "aeb_ar": {"surface_min_m2": " مساحتو {v} متر على الأقل", "budget_max_dt": " عندي {v} دينار", "prix_max_m2_dt": " بأقل من {v} دينار للمتر"},
    "aeb_lat": {"surface_min_m2": " {v} m2 3al a9al", "budget_max_dt": " 3andi {v} dt", "prix_max_m2_dt": " a9al men {v} dt lmetr"},
}
Q_LOTS = {
    "fr": ["je cherche un lot à {lieu}{f}", "lots disponibles à {lieu}{f} ?", "terrain industriel {lieu}{f}",
           "y a-t-il des terrains à {lieu}{f} ?", "je veux acheter un lot a {lieu}{f}"],
    "en": ["I'm looking for an industrial lot in {lieu}{f}", "available plots in {lieu}{f}?", "any industrial land in {lieu}{f}?"],
    "de": ["Ich suche ein Industriegrundstück in {lieu}{f}", "Gibt es Grundstücke in {lieu}{f}?", "Verfügbare Industrieflächen in {lieu}{f}?"],
    "tr": ["{lieu} bölgesinde{f} sanayi arsası arıyorum", "{lieu} bölgesinde{f} sanayi arsası var mı?"],
    "ar": ["أبحث عن مقسم صناعي في {lieu}{f}", "هل توجد أراض صناعية في {lieu}{f}؟", "المقاسم المتاحة في {lieu}{f}"],
    "aeb_ar": ["نحب مقسم صناعي في {lieu}{f}", "فما أراضي صناعية في {lieu}{f}؟", "نلوج على مقسم في {lieu}{f}"],
    "aeb_lat": ["n7eb lot fi {lieu}{f}", "fama terrain industriel fi {lieu}{f}?", "nlawej 3la ma9sem fi {lieu}{f}"],
}
R_LOTS = {
    "fr": ("{n} lots disponibles à {lieu}. Le moins cher : {s} m² à {p} DT/m², soit {t} DT (zone {z}).",
           " Ce prix est le dernier publié par l'AFI : à confirmer auprès d'elle.",
           "Aucun lot disponible à {lieu} avec ces critères. Vous pouvez élargir la recherche ou contacter l'AFI."),
    "en": ("{n} lots available in {lieu}. The cheapest: {s} m² at {p} DT/m², i.e. {t} DT (zone {z}).",
           " This is the last price published by AFI; please confirm it with AFI.",
           "No lots available in {lieu} with these criteria. You can broaden the search or contact AFI."),
    "de": ("{n} Grundstücke in {lieu} verfügbar. Das günstigste: {s} m² zu {p} DT/m², also {t} DT (Zone {z}).",
           " Das ist der zuletzt von der AFI veröffentlichte Preis; bitte bei der AFI bestätigen.",
           "Keine verfügbaren Grundstücke in {lieu} mit diesen Kriterien. Erweitern Sie die Suche oder kontaktieren Sie die AFI."),
    "tr": ("{lieu} bölgesinde {n} arsa mevcut. En ucuzu: {s} m², m² başına {p} DT, toplam {t} DT ({z} bölgesi).",
           " Bu fiyat AFI'nin yayımladığı son fiyattır; lütfen AFI ile teyit edin.",
           "{lieu} bölgesinde bu kriterlere uygun arsa yok. Aramayı genişletebilir veya AFI ile iletişime geçebilirsiniz."),
    "ar": ("عدد المقاسم المتاحة في {lieu}: {n}. الأرخص: {s} م² بسعر {p} دينار للمتر المربع، أي {t} دينار (منطقة {z}).",
           " هذا آخر سعر نشرته الوكالة العقارية الصناعية، يُرجى التأكد منها.",
           "لا توجد مقاسم متاحة في {lieu} بهذه الشروط. يمكنك توسيع البحث أو الاتصال بالوكالة العقارية الصناعية."),
    "aeb_ar": ("فما {n} مقاسم متاحة في {lieu}. الأرخص: {s} متر مربع ب{p} دينار للمتر، يعني {t} دينار (منطقة {z}).",
               " هذا آخر سعر نشراتو الوكالة، أكّد معاهم.",
               "ما فماش مقاسم متاحة في {lieu} بهالشروط. وسّع البحث ولا اتصل بالوكالة."),
    "aeb_lat": ("Fama {n} lots disponibles fi {lieu}. Arkhes wa7ed: {s} m2 b {p} DT lmetr, ya3ni {t} DT (zone {z}).",
                " Hadha e5er soum nachretou l'AFI, aked m3ahom.",
                "Ma famech lots disponibles fi {lieu} b hal chourout. Wassa3 l recherche walla kallem l'AFI."),
}
R_CHOIX = {"fr": "Quel lieu voulez-vous dire ?", "en": "Which place do you mean?", "de": "Welchen Ort meinen Sie?",
           "tr": "Hangi yeri kastediyorsunuz?", "ar": "أي مكان تقصد؟", "aeb_ar": "شنوة المكان اللي تقصد؟",
           "aeb_lat": "Chnoua l blasa elli t9oss?"}

# ------------------------------------------------------------------ zones
Q_ZONES = {"fr": ["quelles zones industrielles à {lieu} ?", "les zones de {lieu}", "zones industrielles dans le gouvernorat de {lieu}"],
           "en": ["which industrial zones are in {lieu}?", "industrial zones in {lieu}"],
           "de": ["Welche Industriegebiete gibt es in {lieu}?"], "tr": ["{lieu} ilindeki sanayi bölgeleri hangileri?"],
           "ar": ["ما هي المناطق الصناعية في {lieu}؟"], "aeb_ar": ["شنية المناطق الصناعية في {lieu}؟"],
           "aeb_lat": ["chnouma les zones industrielles fi {lieu}?"]}
R_ZONES = {"fr": ("{nz} zones avec des lots disponibles à {lieu}, {nl} lots au total.", "Aucune zone avec des lots disponibles à {lieu} actuellement."),
           "en": ("{nz} zones with available lots in {lieu}, {nl} lots in total.", "No zone with available lots in {lieu} at the moment."),
           "de": ("{nz} Gebiete mit verfügbaren Grundstücken in {lieu}, insgesamt {nl} Grundstücke.", "Derzeit kein Gebiet mit verfügbaren Grundstücken in {lieu}."),
           "tr": ("{lieu} ilinde mevcut arsası olan {nz} bölge var, toplam {nl} arsa.", "{lieu} ilinde şu anda mevcut arsası olan bölge yok."),
           "ar": ("في {lieu} عدد المناطق التي فيها مقاسم متاحة: {nz}، ومجموع المقاسم: {nl}.", "لا توجد حاليًا منطقة فيها مقاسم متاحة في {lieu}."),
           "aeb_ar": ("في {lieu} فما {nz} مناطق فيها مقاسم متاحة، {nl} مقسم في المجموع.", "توا ما فماش منطقة فيها مقاسم متاحة في {lieu}."),
           "aeb_lat": ("Fi {lieu} fama {nz} zones fihom lots disponibles, {nl} lots en tout.", "Tawa ma famech zone fiha lots disponibles fi {lieu}.")}

# ------------------------------------------------------------------ fiche d'une zone
Q_FICHE = {"fr": ["prix au m² dans la zone {zone} ?", "infos sur la zone industrielle {zone}", "combien de lots disponibles dans la zone {zone} ?"],
           "en": ["price per m² in the {zone} industrial zone?", "tell me about the {zone} industrial zone"],
           "de": ["Wie hoch ist der Preis pro m² in der Industriezone {zone}?"], "tr": ["{zone} sanayi bölgesinde m² fiyatı ne kadar?"],
           "ar": ["كم سعر المتر المربع في المنطقة الصناعية {zone}؟"], "aeb_ar": ["قداش سوم المتر في المنطقة الصناعية {zone}؟"],
           "aeb_lat": ["9addech soum lmetr fi zone {zone}?"]}
R_FICHE = {"fr": ("La zone {z} ({g}) compte {k} lots disponibles, au prix de {p} DT/m².", " Ce prix est le dernier publié par l'AFI : à confirmer auprès d'elle."),
           "en": ("The {z} zone ({g}) has {k} available lots, at {p} DT/m².", " This is the last price published by AFI; please confirm it with AFI."),
           "de": ("Die Zone {z} ({g}) hat {k} verfügbare Grundstücke, zu {p} DT/m².", " Das ist der zuletzt von der AFI veröffentlichte Preis; bitte bei der AFI bestätigen."),
           "tr": ("{z} bölgesinde ({g}) {k} arsa mevcut, m² fiyatı {p} DT.", " Bu fiyat AFI'nin yayımladığı son fiyattır; lütfen AFI ile teyit edin."),
           "ar": ("في منطقة {z} ({g}) عدد المقاسم المتاحة: {k}، بسعر {p} دينار للمتر المربع.", " هذا آخر سعر نشرته الوكالة العقارية الصناعية، يُرجى التأكد منها."),
           "aeb_ar": ("منطقة {z} ({g}) فيها {k} مقاسم متاحة، بسوم {p} دينار للمتر.", " هذا آخر سعر نشراتو الوكالة، أكّد معاهم."),
           "aeb_lat": ("Zone {z} ({g}) fiha {k} lots disponibles, b {p} DT lmetr.", " Hadha e5er soum nachretou l'AFI, aked m3ahom.")}

# ------------------------------------------------------------------ projets (conseiller)
PROJETS = [  # (description en français passée à l'outil, {langue: description du visiteur})
    ("transformation de poisson", {"fr": "une usine de transformation de poisson", "en": "a fish processing plant", "de": "eine Fischverarbeitungsfabrik",
     "tr": "bir balık işleme fabrikası", "ar": "مصنع لتحويل الأسماك", "aeb_ar": "معمل تحويل حوت", "aeb_lat": "usine ta7wil 7out"}),
    ("fabrication d'emballages en plastique", {"fr": "une usine d'emballages en plastique", "en": "a plastic packaging factory",
     "de": "eine Fabrik für Kunststoffverpackungen", "tr": "plastik ambalaj fabrikası", "ar": "مصنع للتغليف البلاستيكي",
     "aeb_ar": "معمل بلاستيك متاع تغليف", "aeb_lat": "usine mta3 plastique"}),
    ("confection de vêtements", {"fr": "un atelier de confection de vêtements", "en": "a clothing manufacturing workshop",
     "de": "eine Bekleidungsfabrik", "tr": "bir hazır giyim atölyesi", "ar": "ورشة لصناعة الملابس", "aeb_ar": "معمل خياطة حوايج",
     "aeb_lat": "atelier khiyata"}),
    ("fabrication de meubles en bois", {"fr": "une menuiserie de meubles en bois", "en": "a wooden furniture factory",
     "de": "eine Möbeltischlerei", "tr": "ahşap mobilya fabrikası", "ar": "مصنع أثاث خشبي", "aeb_ar": "معمل موبيليا عود",
     "aeb_lat": "usine meubles bel 3oud"}),
    ("fabrication de pièces automobiles", {"fr": "une usine de pièces automobiles", "en": "a car parts factory", "de": "eine Fabrik für Autoteile",
     "tr": "otomotiv yedek parça fabrikası", "ar": "مصنع قطع غيار السيارات", "aeb_ar": "معمل قطع غيار كراهب",
     "aeb_lat": "usine pièces de rechange karahib"}),
    ("production d'huile d'olive", {"fr": "une huilerie d'huile d'olive", "en": "an olive oil mill", "de": "eine Olivenölmühle",
     "tr": "zeytinyağı fabrikası", "ar": "معصرة لزيت الزيتون", "aeb_ar": "معصرة زيت زيتون", "aeb_lat": "ma3sra zit zitoun"}),
    ("fabrication de briques et matériaux de construction", {"fr": "une briqueterie", "en": "a brick factory", "de": "eine Ziegelei",
     "tr": "tuğla fabrikası", "ar": "مصنع للآجر", "aeb_ar": "معمل ياجور", "aeb_lat": "usine yajour"}),
    ("fabrication de produits pharmaceutiques", {"fr": "un laboratoire de médicaments", "en": "a pharmaceutical plant",
     "de": "ein Pharmawerk", "tr": "ilaç fabrikası", "ar": "مصنع للأدوية", "aeb_ar": "معمل دواء", "aeb_lat": "usine dwe"}),
]
Q_PROJET = {"fr": ["je veux créer {p}, que me conseillez-vous ?", "projet : {p}, par où commencer ?"],
            "en": ["I want to set up {p}, what do you advise?"], "de": ["Ich möchte {p} gründen. Was raten Sie mir?"],
            "tr": ["{p} kurmak istiyorum, ne önerirsiniz?"], "ar": ["أريد إنشاء {p}، بماذا تنصحني؟"],
            "aeb_ar": ["نحب نعمل {p}، كيفاش نبدا؟"], "aeb_lat": ["n7eb na3mel {p}, kifech nebda?"]}
R_PROJET = {"fr": "Pour ce projet, l'activité la plus proche est « {a} ». Organismes compétents selon le montant de l'investissement : {o}.",
            "en": "For this project, the closest activity is “{a}”. Competent bodies depending on the investment amount: {o}.",
            "de": "Für dieses Projekt ist die nächstliegende Tätigkeit „{a}“. Zuständige Stellen je nach Investitionsbetrag: {o}.",
            "tr": "Bu proje için en yakın faaliyet: “{a}”. Yatırım tutarına göre yetkili kurumlar: {o}.",
            "ar": "أقرب نشاط لهذا المشروع هو «{a}». الهياكل المختصة حسب مبلغ الاستثمار: {o}.",
            "aeb_ar": "أقرب نشاط لمشروعك هو «{a}». الهياكل المختصة حسب قداش تستثمر: {o}.",
            "aeb_lat": "A9rab activité l projet mte3ek hiya « {a} ». Les organismes 7asb 9addech testathmer: {o}."}

# ------------------------------------------------------------------ hors sujet
HORS_SUJET = {"fr": ["comment faire un gâteau ?", "qui va gagner le match ce soir ?", "quel temps fera-t-il demain ?", "bonjour", "merci beaucoup"],
              "en": ["how do I bake a cake?", "who won the football game?", "hello", "thanks a lot"],
              "de": ["Wie backe ich einen Kuchen?", "Wie wird das Wetter morgen?", "Hallo", "Vielen Dank"],
              "tr": ["Kek nasıl yapılır?", "Yarın hava nasıl olacak?", "Merhaba", "Çok teşekkürler"],
              "ar": ["كيف أحضر كعكة؟", "من فاز في المباراة؟", "مرحبا", "شكرا جزيلا"],
              "aeb_ar": ["كيفاش نعمل كيكة؟", "شكون ربح الماتش؟", "عسلامة", "يعيشك"],
              "aeb_lat": ["kifech na3mel gateau?", "chkoun reb7 el match?", "3aslema", "y3aychek"]}
R_HORS = {"fr": ("Je ne peux pas vous aider pour cela. Je vous aide à trouver un lot ou une zone industrielle, et pour les démarches de l'AFI, les incitations et les organismes d'investissement.",
                 "Bonjour ! Je vous aide à trouver un lot ou une zone industrielle, et pour les démarches de l'AFI. Que cherchez-vous ?"),
          "en": ("I can't help with that. I help you find an industrial lot or zone, and with AFI procedures, incentives and investment bodies.",
                 "Hello! I help you find an industrial lot or zone, and with AFI procedures. What are you looking for?"),
          "de": ("Dabei kann ich Ihnen nicht helfen. Ich helfe Ihnen, ein Industriegrundstück oder -gebiet zu finden, sowie bei den Verfahren der AFI, Förderungen und Investitionsstellen.",
                 "Hallo! Ich helfe Ihnen, ein Industriegrundstück oder -gebiet zu finden, und bei den Verfahren der AFI. Was suchen Sie?"),
          "tr": ("Bu konuda yardımcı olamıyorum. Sanayi arsası veya bölgesi bulmanıza, AFI işlemlerine, teşviklere ve yatırım kurumlarına yardımcı oluyorum.",
                 "Merhaba! Sanayi arsası veya bölgesi bulmanıza ve AFI işlemlerine yardımcı oluyorum. Ne arıyorsunuz?"),
          "ar": ("لا يمكنني مساعدتك في هذا. أساعدك في إيجاد مقسم أو منطقة صناعية، وفي إجراءات الوكالة العقارية الصناعية والحوافز وهياكل الاستثمار.",
                 "مرحبًا! أساعدك في إيجاد مقسم أو منطقة صناعية، وفي إجراءات الوكالة العقارية الصناعية. عمّ تبحث؟"),
          "aeb_ar": ("ما نجمش نعاونك في هذا. نعاونك تلقى مقسم ولا منطقة صناعية، وفي إجراءات الوكالة والحوافز.",
                     "عسلامة! نعاونك تلقى مقسم ولا منطقة صناعية، وفي إجراءات الوكالة. شنوة تلوج؟"),
          "aeb_lat": ("Ma nejjemch n3awnek fi hadha. N3awnek tal9a lot walla zone industrielle, w fi l procédures mta3 l'AFI.",
                      "3aslema! N3awnek tal9a lot walla zone industrielle, w fi l procédures mta3 l'AFI. Chnoua tlawej?")}
SALUTATIONS = {"bonjour", "merci beaucoup", "hello", "thanks a lot", "Hallo", "Vielen Dank", "Merhaba", "Çok teşekkürler",
               "مرحبا", "شكرا جزيلا", "عسلامة", "يعيشك", "3aslema", "y3aychek", "salam", "saha", "السلام عليكم", "مشكور"}

# ------------------------------------------------------------------ démarches et passages (réponses du modèle enseignant)
SERVICES = {
    "acquisition": {"fr": "comment acheter un lot industriel auprès de l'AFI ?", "en": "how do I buy an industrial lot from AFI?",
                    "de": "Wie kaufe ich ein Industriegrundstück bei der AFI?", "tr": "AFI'den sanayi arsası nasıl satın alırım?",
                    "ar": "ما هي إجراءات اقتناء مقسم صناعي؟", "aeb_ar": "شنوة الأوراق اللازمة باش نشري مقسم صناعي؟",
                    "aeb_lat": "chnowa lwra9 lazmin bech nechri ma9sem sina3i?"},
    "encheres": {"fr": "comment participer à une vente aux enchères de l'AFI ?", "en": "how do AFI public auctions work?",
                 "de": "Wie funktionieren die Versteigerungen der AFI?", "tr": "AFI açık artırmalarına nasıl katılırım?",
                 "ar": "كيف أشارك في البتة العمومية للوكالة؟", "aeb_ar": "كيفاش نشارك في البتة متاع الوكالة؟",
                 "aeb_lat": "kifech nocharek fi l bta mta3 l'AFI?"},
    "insertion_hypotheque": {"fr": "la banque me demande une attestation pour mon prêt", "en": "my bank asks for a mortgage certificate for my loan",
                             "de": "Meine Bank verlangt eine Hypothekenbescheinigung für meinen Kredit", "tr": "Banka kredim için ipotek belgesi istiyor",
                             "ar": "البنك يطلب مني شهادة ترسيم رهن من أجل القرض", "aeb_ar": "البنكة طلبت مني ورقة باش ناخو كريدي",
                             "aeb_lat": "el banka tlabet menni war9a bech na5ou crédit"},
    "mainlevee": {"fr": "comment obtenir la mainlevée sur mon terrain ?", "en": "how do I get the release of the restriction on my land?",
                  "de": "Wie erhalte ich die Löschung der Belastung auf meinem Grundstück?", "tr": "Arazimdeki kısıtlamanın kaldırılmasını nasıl alırım?",
                  "ar": "كيف أتحصل على رفع اليد على أرضي؟", "aeb_ar": "كيفاش ناخو رفع اليد على الأرض متاعي؟",
                  "aeb_lat": "kifech na5ou raf3 el yed 3al ardh mte3i?"},
    "situation_fonciere": {"fr": "je veux une attestation de situation foncière", "en": "I need a land status certificate",
                           "de": "Ich brauche eine Bescheinigung über den Grundstücksstatus", "tr": "Arazi durum belgesine ihtiyacım var",
                           "ar": "أريد شهادة في الوضعية العقارية", "aeb_ar": "نحب شهادة في الوضعية العقارية متاع المقسم",
                           "aeb_lat": "n7eb chahada fi wadh3iya 3a9ariya mta3 el ma9sem"},
}
PASSAGES = {  # question en français passée à l'outil -> {langue: question du visiteur}
    "qu'est-ce que l'AFI, l'Agence Foncière Industrielle ?": {"fr": "c'est quoi l'AFI ?", "en": "what is AFI?", "de": "Was ist die AFI?",
        "tr": "AFI nedir?", "ar": "ما هي الوكالة العقارية الصناعية؟", "aeb_ar": "شنية الوكالة العقارية الصناعية؟",
        "aeb_lat": "chnia l'AFI?"},
    "incitations et primes dans les zones de développement régional": {"fr": "quelles incitations dans les zones de développement régional ?",
        "en": "what incentives are there in regional development zones?", "de": "Welche Förderungen gibt es in den Regionalentwicklungsgebieten?",
        "tr": "Bölgesel kalkınma bölgelerinde hangi teşvikler var?", "ar": "ما هي الحوافز في مناطق التنمية الجهوية؟",
        "aeb_ar": "شنية الحوافز في مناطق التنمية الجهوية؟", "aeb_lat": "chnouma les avantages fi zones de développement régional?"},
    "rôle et services de la TIA, Instance Tunisienne de l'Investissement": {"fr": "c'est quoi la TIA ?", "en": "what does the TIA do?",
        "de": "Was macht die TIA?", "tr": "TIA ne yapar?", "ar": "ما هي الهيئة التونسية للاستثمار؟", "aeb_ar": "شنية الهيئة التونسية للاستثمار؟",
        "aeb_lat": "chnia la TIA?"},
    "contacter l'APII, Agence de Promotion de l'Industrie et de l'Innovation": {"fr": "comment contacter l'APII ?", "en": "how can I contact APII?",
        "de": "Wie erreiche ich die APII?", "tr": "APII ile nasıl iletişime geçerim?", "ar": "كيف أتصل بوكالة النهوض بالصناعة والتجديد؟",
        "aeb_ar": "كيفاش نتصل بالـAPII؟", "aeb_lat": "kifech nkallem l'APII?"},
    "le président directeur général de l'AFI": {"fr": "qui est le PDG de l'AFI ?", "en": "who is the CEO of AFI?", "de": "Wer ist der Generaldirektor der AFI?",
        "tr": "AFI'nin genel müdürü kim?", "ar": "من هو الرئيس المدير العام للوكالة العقارية الصناعية؟", "aeb_ar": "شكون الرئيس المدير العام متاع الوكالة؟",
        "aeb_lat": "chkoun el PDG mta3 l'AFI?"},
}


def _fmt(x):
    return _n(x)


def _lieux():
    """Gouvernorats (nom français et arabe) ; Grand Tunis en plus pour les écritures latines."""
    g = [(r["nom_fr"], r["nom_ar"]) for r in q("SELECT nom_fr, nom_ar FROM dalila_gouvernorats ORDER BY code")]
    return g + [("Grand Tunis", None)]


def _zones():
    return [(r["nom_fr"], r["nom_ar"]) for r in q("SELECT nom_fr, nom_ar FROM v_pub_zones ORDER BY lots_disponibles DESC")]


def _conv(question, lang, nom, args, res, reponse):
    tool_txt = vue(nom, res)
    rappel = RAPPEL_LANGUE.format(message=question[:200], interface="")
    return {"langue": lang, "outil": nom, "messages": [
        systeme(), {"role": "user", "content": question},
        {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {
            "name": nom, "arguments": dict(sorted(args.items()))}}]},
        {"role": "tool", "name": nom, "content": tool_txt},
        {"role": "user", "content": rappel},
        {"role": "assistant", "content": reponse}]}


def _valide(ex, resultats):
    r = ex["messages"][-1]["content"]
    return verifier_ancrage(r, resultats, ex["messages"][1]["content"])["ok"] and not degenere(r)


def ex_lots(rnd):
    out = []
    for lang in LANGUES:
        for fr, ar in _lieux() * 2:
            lieu = ar if lang in ARABE else fr
            if not lieu:
                continue
            champ = rnd.choice([None, "surface_min_m2", "budget_max_dt", "prix_max_m2_dt"])
            val = {"surface_min_m2": rnd.choice([500, 1000, 2000, 5000]), "budget_max_dt": rnd.choice([50000, 100000, 200000]),
                   "prix_max_m2_dt": rnd.choice([20, 30, 50])}.get(champ)
            f = FILTRES[lang][champ].format(v=val) if champ else ""
            question = rnd.choice(Q_LOTS[lang]).format(lieu=lieu, f=f)
            args = {"lieu": lieu, **({champ: val} if champ else {})}
            res, args = appeler_avec_lieu("chercher_lots", args, question)
            if "erreur" in res:
                continue
            if res.get("lieux_a_proposer"):
                reponse = R_CHOIX[lang]
            elif not res.get("nombre_total"):
                reponse = R_LOTS[lang][2].format(lieu=lieu)
            else:
                l0 = res["lots"][0]
                if l0.get("prix_m2_dt") is None:
                    continue
                reponse = R_LOTS[lang][0].format(n=res["nombre_total"], lieu=lieu, s=_fmt(l0["surface_m2"]), p=_fmt(l0["prix_m2_dt"]),
                                                 t=_fmt(l0["prix_total_dt"]), z=l0["zone"])
                if "dernier" in (l0.get("prix_selon") or ""):
                    reponse += R_LOTS[lang][1]
            ex = _conv(question, lang, "chercher_lots", args, res, reponse)
            if _valide(ex, [res]):
                out.append(ex)
    # lieu ambigu : question à choix
    for lang in LANGUES:
        lieu = "تونس" if lang in ARABE else "tunis"
        question = Q_LOTS[lang][0].format(lieu=lieu, f="")
        res, args = appeler_avec_lieu("chercher_lots", {"lieu": lieu}, question)
        if res.get("lieux_a_proposer"):
            out.append(_conv(question, lang, "chercher_lots", args, res, R_CHOIX[lang]))
    return out


def ex_zones(rnd):
    out = []
    for lang in LANGUES:
        for fr, ar in rnd.sample(_lieux(), 12):
            lieu = ar if lang in ARABE else fr
            if not lieu:
                continue
            question = rnd.choice(Q_ZONES[lang]).format(lieu=lieu)
            res, args = appeler_avec_lieu("lister_zones", {"lieu": lieu}, question)
            if "erreur" in res or res.get("lieux_a_proposer") or res.get("nombre") is None:
                continue
            reponse = (R_ZONES[lang][0].format(nz=res["nombre"], nl=res["lots_disponibles_total"], lieu=lieu)
                       if res["nombre"] else R_ZONES[lang][1].format(lieu=lieu))
            ex = _conv(question, lang, "lister_zones", args, res, reponse)
            if _valide(ex, [res]):
                out.append(ex)
    return out


def ex_fiches(rnd):
    from dalila.traitement.registre import appeler
    out = []
    zones = _zones()
    for lang in LANGUES:
        for fr, ar in rnd.sample(zones, 14):
            nom = ar if lang in ARABE else fr
            if not nom:
                continue
            res = appeler("fiche_zone", {"zone_id": nom})
            if not res.get("zone_id") or res.get("prix_en_conflit"):
                continue
            prix, dernier = res.get("prix_m2_dt"), False
            if prix is None:
                prix, dernier = res.get("prix_m2_dernier_publie_dt"), True
            if prix is None:
                continue
            question = rnd.choice(Q_FICHE[lang]).format(zone=nom)
            reponse = R_FICHE[lang][0].format(z=res["nom"], g=res["gouvernorat"], k=res["lots_disponibles"], p=_fmt(prix))
            if dernier:
                reponse += R_FICHE[lang][1]
            ex = _conv(question, lang, "fiche_zone", {"zone_id": nom}, res, reponse)
            if _valide(ex, [res]):
                out.append(ex)
    return out


def ex_projets(rnd):
    from dalila.traitement.registre import appeler
    out = []
    for secteur, textes in PROJETS:
        res = appeler("conseiller", {"secteur": secteur})
        if "erreur" in res or not res.get("activites"):
            continue
        orgs = ", ".join(f"{o['nom']} ({o['id']})" for o in res.get("organismes", [])) or "APII"
        for lang in LANGUES:
            question = rnd.choice(Q_PROJET[lang]).format(p=textes[lang])
            reponse = R_PROJET[lang].format(a=res["activites"][0]["libelle"], o=orgs)
            ex = _conv(question, lang, "conseiller", {"secteur": secteur}, res, reponse)
            if _valide(ex, [res]):
                out.append(ex)
    return out


def ex_hors_sujet():
    out = []
    for lang in LANGUES:
        for question in HORS_SUJET[lang]:
            reponse = R_HORS[lang][1 if question in SALUTATIONS else 0]
            out.append(_conv(question, lang, "hors_sujet", {}, CONSIGNE_HORS_SUJET, reponse))
    return out


# ------------------------------------------------------------------ enseignant : le modèle local, sur carte graphique
def _ecriture_ok(lang, texte):
    arabes = sum(1 for c in texte if "؀" <= c <= "ۿ")
    lettres = sum(1 for c in texte if c.isalpha()) or 1
    if lang in ARABE:
        return arabes / lettres > 0.5
    if arabes / lettres > 0.05:
        return False
    if lang in ("en", "de", "tr"):  # contrôle des données d'entraînement seulement (pas une règle du service)
        return len(re.findall(r"\b(le|la|les|des|est|pour|une|vous)\b", texte.lower())) <= 1
    return True


NOMS_LANGUE = {"en": "anglais", "de": "allemand", "tr": "turc", "ar": "arabe standard",
               "aeb_ar": "dialecte tunisien écrit en lettres arabes", "aeb_lat": "dialecte tunisien écrit en lettres latines (arabizi)"}


def ex_enseignant():
    from dalila.moteurs.llm import discuter
    from dalila.traitement.registre import appeler
    outils = Agent().outils
    cas = [("demarche", {"service": s}, t) for s, t in SERVICES.items()] + \
          [("chercher_passages", {"question": qfr}, t) for qfr, t in PASSAGES.items()]
    out, rejetes = [], 0

    def controle(texte, res, question, lang):
        return verifier_ancrage(texte, [res], question)["ok"] and not degenere(texte) and _ecriture_ok(lang, texte)

    for nom, args, textes in cas:
        res = appeler(nom, args)
        francais = None
        for lang in LANGUES:  # le français d'abord : sa réponse sert de base aux traductions
            question = textes[lang]
            ex = _conv(question, lang, nom, args, res, "")
            garde = None
            for temperature in (0.0, 0.4, 0.7):
                r = discuter(ex["messages"][:-1], outils=outils, delai_s=180, temperature=temperature, jetons_max=160)
                texte = r["content"].strip()
                if r["tool_calls"] or not texte or r["fin"] == "length":
                    continue
                if controle(texte, res, question, lang):
                    garde = texte
                    break
            if not garde and francais and lang in NOMS_LANGUE:  # répondre est trop dur : traduire la réponse française
                for temperature in (0.0, 0.4):
                    r = discuter([{"role": "user", "content": f"Traduis ce texte en {NOMS_LANGUE[lang]}. Garde les nombres, "
                                   f"les sigles et les noms propres tels quels. Écris seulement la traduction.\n\n{francais}"}],
                                 delai_s=180, temperature=temperature, jetons_max=200)
                    texte = r["content"].strip()
                    if texte and r["fin"] != "length" and controle(texte, res, question, lang):
                        garde = texte
                        break
            if lang == "fr":
                francais = garde
            if garde:
                ex["messages"][-1]["content"] = garde
                out.append(ex)
            else:
                rejetes += 1
            print(f"  {nom} {lang}: {'gardé' if garde else 'rejeté'}", flush=True)
    print(f"enseignant : {len(out)} gardés, {rejetes} rejetés")
    return out


def _sans_fuite(exemples):
    """Aucune question du jeu de test (vraies questions) dans l'entraînement."""
    def norm(t):
        return re.sub(r"\W+", " ", t.lower()).strip()
    test = {norm(r["question"]) for r in csv.DictReader(open(RACINE / "eval/testset/questions_reelles.csv", encoding="utf-8-sig"))}
    return [e for e in exemples if norm(e["messages"][1]["content"]) not in test]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enseignant", action="store_true")
    ap.add_argument("--graine", type=int, default=7)
    ap.add_argument("--reel", action="store_true", help="ajoute les conversations réussies exportées "
                                                         "(dalila.apprentissage.exporter -> reel.jsonl)")
    a = ap.parse_args()
    rnd = random.Random(a.graine)
    exemples = ex_lots(rnd) + ex_zones(rnd) + ex_fiches(rnd) + ex_projets(rnd) + ex_hors_sujet()
    if a.enseignant:
        exemples += ex_enseignant()
    if a.reel and (SORTIE / "reel.jsonl").exists():
        reels = [json.loads(l) for l in open(SORTIE / "reel.jsonl", encoding="utf-8")]
        print(len(reels), "exemples tirés de vraies conversations")
        exemples += reels
    exemples = _sans_fuite(exemples)
    rnd.shuffle(exemples)
    SORTIE.mkdir(parents=True, exist_ok=True)
    nval = max(20, len(exemples) // 20)
    for nom, part in (("val", exemples[:nval]), ("train", exemples[nval:])):
        with open(SORTIE / f"{nom}.jsonl", "w", encoding="utf-8") as f:
            for e in part:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    (SORTIE / "outils.json").write_text(json.dumps(Agent().outils, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(len(exemples), "exemples ;", dict(Counter(e["outil"] for e in exemples)), dict(Counter(e["langue"] for e in exemples)))


if __name__ == "__main__":
    main()
