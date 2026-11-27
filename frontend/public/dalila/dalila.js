/*
 * Dalila : la fenêtre de conversation à ajouter sur la carte interactive de l'AFI.
 *
 * Une seule ligne dans la page de la carte (dalila.css est chargé automatiquement, à côté de ce fichier) :
 *
 *   <script src="/dalila/dalila.js" data-api="https://dalila.afi.nat.tn" data-lang="fr" defer></script>
 *
 * Appelle l'API du module dalila/communication :
 *   POST /carte/chatbot          question -> réponse avec balises [[ZONE]], [[LOT]], [[CHOIX]], [[PDF]]
 *   POST /carte/chatbot/avis     utile / pas utile
 *   POST /carte/voix/transcrire  micro -> texte (affiché et modifiable AVANT l'envoi)
 *   POST /carte/voix/lire        réponse -> voix (204 : pas de voix pour cette écriture, le texte reste)
 *   GET  /sante                  service prêt ?
 *
 * Lien avec la carte (dans les deux sens) :
 *   la carte -> Dalila : Dalila.definirContexte({zone: 12, nom: "Sejnane"})   ou  Dalila.demander("…", contexte)
 *   Dalila -> la carte : événements « dalila:zone » et « dalila:lot » sur window, detail = {id, nom}
 *                        (clic sur une zone ou un lot cité dans une réponse : la carte les centre)
 *
 * Le texte des réponses est toujours inséré comme texte (jamais comme HTML) ; seuls les liens http(s) sont rendus.
 */
(function () {
  "use strict";
  if (window.Dalila) return;

  var script = document.currentScript;
  var API = ((script && script.getAttribute("data-api")) || "").replace(/\/+$/, "");
  var BASE = script && script.src ? script.src.replace(/[^\/]*$/, "") : "";   // dossier de dalila.js
  var DELAI_MS = 90000;           // l'API répond en 35 s au plus ; marge pour un processeur chargé
  var HISTORIQUE_MAX = 20;        // l'API garde les 20 derniers messages
  var TAILLE_MAX = 500;           // l'agent lit 500 caractères au plus
  var RTL = { ar: 1, aeb: 1, arq: 1, ayl: 1 };

  /* ------------------------------------------------------------------ textes de l'interface (8 langues) */
  var ar = {
    nom: "دليلة", sousTitre: "مساعدة الوكالة العقارية الصناعية", ouvrir: "اسأل دليلة", fermer: "إغلاق",
    langue: "اللغة", saisie: "سؤالك", placeholder: "اكتب سؤالك…", envoyer: "إرسال",
    micro: "التحدث", arreter: "إيقاف التسجيل",
    accueilTitre: "مرحبًا، أنا دليلة",
    accueil: "أساعدك في إيجاد مقسم صناعي، ومعرفة الأسعار والوثائق والإجراءات لدى الوكالة العقارية الصناعية.",
    suggestions: ["مقسم 3000 م² في بنزرت", "ما هي الوثائق اللازمة لشراء مقسم؟", "مناطق صناعية قريبة من ميناء صفاقس"],
    reflechit: "أبحث في قاعدة بيانات الوكالة…", secondes: "ث",
    ecoute: "أستمع… اضغط مرة أخرى للإيقاف", transcription: "أكتب ما قلته…",
    verifier: "تحقق من النص ثم أرسله.", microIndispo: "الميكروفون غير متاح",
    consentTitre: "أول استعمال للميكروفون",
    consent: "دليلة تستمع فقط عندما تضغط على الميكروفون. الصوت يُستعمل لكتابة سؤالك ولا يُحفظ.",
    autoriser: "السماح بالميكروفون", ecrire: "أفضّل الكتابة",
    lire: "استمع إلى الإجابة", stop: "إيقاف القراءة", pasDeVoix: "لا يوجد صوت لهذه الكتابة: تبقى الإجابة مكتوبة.",
    utile: "إجابة مفيدة", pasUtile: "إجابة غير مفيدة", merci: "شكرًا على رأيك",
    voirCarte: "عرض على الخريطة", lot: "مقسم",
    contexte: "من الخريطة:", retirer: "إزالة",
    preparation: "دليلة تستعد (حوالي دقيقة واحدة)…",
    horsService: "دليلة غير متاحة حاليًا. اتصل بالوكالة: ‎+216 71 124 260",
    delai: "انتهت مهلة الانتظار. أعد المحاولة أو اتصل بالوكالة: ‎+216 71 124 260",
    pied: "قد تخطئ دليلة: الأرقام مأخوذة من قاعدة بيانات الوكالة، تحقق منها لدى الوكالة.",
    sources: "المصادر:"
  };
  var TEXTES = {
    fr: {
      nom: "Dalila", sousTitre: "Conseillère de l'AFI", ouvrir: "Demander à Dalila", fermer: "Fermer",
      langue: "Langue", saisie: "Votre question", placeholder: "Votre question…", envoyer: "Envoyer",
      micro: "Parler", arreter: "Arrêter l'enregistrement",
      accueilTitre: "Bonjour, je suis Dalila",
      accueil: "Je vous aide à trouver un lot industriel, à connaître les prix, les documents et les démarches de l'AFI.",
      suggestions: ["Un lot de 3 000 m² à Bizerte", "Quels documents pour acheter un lot ?", "Zones proches du port de Sfax"],
      reflechit: "Je consulte la base de l'AFI…", secondes: "s",
      ecoute: "J'écoute… appuyez de nouveau pour arrêter", transcription: "J'écris ce que vous avez dit…",
      verifier: "Vérifiez le texte, puis envoyez.", microIndispo: "Micro indisponible",
      consentTitre: "Premier usage du micro",
      consent: "Dalila écoute seulement quand vous appuyez sur le micro. L'audio sert à transcrire votre question et n'est pas conservé.",
      autoriser: "Autoriser le micro", ecrire: "Écrire plutôt",
      lire: "Écouter la réponse", stop: "Arrêter la lecture", pasDeVoix: "Pas de voix pour cette écriture : la réponse reste en texte.",
      utile: "Réponse utile", pasUtile: "Réponse pas utile", merci: "Merci pour votre avis",
      voirCarte: "Voir sur la carte", lot: "Lot",
      contexte: "Depuis la carte :", retirer: "Retirer",
      preparation: "Dalila se prépare (environ une minute)…",
      horsService: "Dalila n'est pas disponible pour le moment. Contactez l'AFI : +216 71 124 260.",
      delai: "La réponse a pris trop de temps. Réessayez, ou contactez l'AFI : +216 71 124 260.",
      pied: "Dalila peut se tromper : les chiffres viennent de la base AFI, vérifiez auprès de l'AFI.",
      sources: "Sources :"
    },
    en: {
      nom: "Dalila", sousTitre: "AFI advisor", ouvrir: "Ask Dalila", fermer: "Close",
      langue: "Language", saisie: "Your question", placeholder: "Your question…", envoyer: "Send",
      micro: "Speak", arreter: "Stop recording",
      accueilTitre: "Hello, I'm Dalila",
      accueil: "I help you find an industrial lot and learn about AFI prices, documents and procedures.",
      suggestions: ["A 3,000 m² lot in Bizerte", "Which documents do I need to buy a lot?", "Zones near the port of Sfax"],
      reflechit: "Checking the AFI database…", secondes: "s",
      ecoute: "Listening… press again to stop", transcription: "Writing down what you said…",
      verifier: "Check the text, then send it.", microIndispo: "Microphone unavailable",
      consentTitre: "Using the microphone",
      consent: "Dalila only listens while you press the microphone. The audio is used to transcribe your question and is not kept.",
      autoriser: "Allow microphone", ecrire: "Type instead",
      lire: "Listen to the answer", stop: "Stop reading", pasDeVoix: "No voice for this script: the answer stays as text.",
      utile: "Helpful answer", pasUtile: "Not helpful", merci: "Thanks for your feedback",
      voirCarte: "Show on the map", lot: "Lot",
      contexte: "From the map:", retirer: "Remove",
      preparation: "Dalila is getting ready (about a minute)…",
      horsService: "Dalila is not available right now. Contact AFI: +216 71 124 260.",
      delai: "The answer took too long. Try again, or contact AFI: +216 71 124 260.",
      pied: "Dalila can make mistakes: figures come from the AFI database, please check with AFI.",
      sources: "Sources:"
    },
    de: {
      nom: "Dalila", sousTitre: "Beraterin der AFI", ouvrir: "Dalila fragen", fermer: "Schließen",
      langue: "Sprache", saisie: "Ihre Frage", placeholder: "Ihre Frage…", envoyer: "Senden",
      micro: "Sprechen", arreter: "Aufnahme beenden",
      accueilTitre: "Hallo, ich bin Dalila",
      accueil: "Ich helfe Ihnen, ein Industriegrundstück zu finden, und informiere über Preise, Unterlagen und Verfahren der AFI.",
      suggestions: ["Ein Grundstück mit 3.000 m² in Bizerte", "Welche Unterlagen brauche ich für den Kauf?", "Zonen nahe dem Hafen von Sfax"],
      reflechit: "Ich prüfe die AFI-Datenbank…", secondes: "s",
      ecoute: "Ich höre zu… zum Beenden erneut drücken", transcription: "Ich schreibe auf, was Sie gesagt haben…",
      verifier: "Prüfen Sie den Text und senden Sie ihn dann.", microIndispo: "Mikrofon nicht verfügbar",
      consentTitre: "Mikrofon verwenden",
      consent: "Dalila hört nur zu, während Sie das Mikrofon drücken. Die Aufnahme dient nur der Abschrift und wird nicht gespeichert.",
      autoriser: "Mikrofon erlauben", ecrire: "Lieber schreiben",
      lire: "Antwort anhören", stop: "Vorlesen beenden", pasDeVoix: "Keine Stimme für diese Schrift: Die Antwort bleibt als Text.",
      utile: "Hilfreiche Antwort", pasUtile: "Nicht hilfreich", merci: "Danke für Ihre Rückmeldung",
      voirCarte: "Auf der Karte zeigen", lot: "Grundstück",
      contexte: "Von der Karte:", retirer: "Entfernen",
      preparation: "Dalila wird vorbereitet (etwa eine Minute)…",
      horsService: "Dalila ist im Moment nicht verfügbar. Kontakt AFI: +216 71 124 260.",
      delai: "Die Antwort hat zu lange gedauert. Bitte erneut versuchen oder AFI kontaktieren: +216 71 124 260.",
      pied: "Dalila kann sich irren: Die Zahlen stammen aus der AFI-Datenbank, bitte bei der AFI prüfen.",
      sources: "Quellen:"
    },
    tr: {
      nom: "Dalila", sousTitre: "AFI danışmanı", ouvrir: "Dalila'ya sor", fermer: "Kapat",
      langue: "Dil", saisie: "Sorunuz", placeholder: "Sorunuz…", envoyer: "Gönder",
      micro: "Konuş", arreter: "Kaydı durdur",
      accueilTitre: "Merhaba, ben Dalila",
      accueil: "Sanayi arsası bulmanıza ve AFI'nin fiyatları, belgeleri ve işlemleri hakkında bilgi almanıza yardımcı olurum.",
      suggestions: ["Bizerte'de 3.000 m² arsa", "Arsa almak için hangi belgeler gerekir?", "Sfax limanına yakın bölgeler"],
      reflechit: "AFI veritabanına bakıyorum…", secondes: "sn",
      ecoute: "Dinliyorum… durdurmak için tekrar basın", transcription: "Söylediklerinizi yazıyorum…",
      verifier: "Metni kontrol edin, sonra gönderin.", microIndispo: "Mikrofon kullanılamıyor",
      consentTitre: "Mikrofon kullanımı",
      consent: "Dalila yalnızca mikrofona bastığınızda dinler. Ses yalnızca sorunuzu yazıya dökmek için kullanılır ve saklanmaz.",
      autoriser: "Mikrofona izin ver", ecrire: "Yazmayı tercih et",
      lire: "Yanıtı dinle", stop: "Okumayı durdur", pasDeVoix: "Bu yazı için ses yok: yanıt metin olarak kalır.",
      utile: "Faydalı yanıt", pasUtile: "Faydalı değil", merci: "Geri bildiriminiz için teşekkürler",
      voirCarte: "Haritada göster", lot: "Arsa",
      contexte: "Haritadan:", retirer: "Kaldır",
      preparation: "Dalila hazırlanıyor (yaklaşık bir dakika)…",
      horsService: "Dalila şu anda kullanılamıyor. AFI ile iletişime geçin: +216 71 124 260.",
      delai: "Yanıt çok uzun sürdü. Tekrar deneyin veya AFI ile iletişime geçin: +216 71 124 260.",
      pied: "Dalila hata yapabilir: rakamlar AFI veritabanından gelir, lütfen AFI ile doğrulayın.",
      sources: "Kaynaklar:"
    },
    ar: ar,
    // dialectes : interface en arabe ; l'accueil dans le dialecte (à faire relire par un locuteur)
    aeb: Object.assign({}, ar, { accueilTitre: "عسلامة، أنا دليلة",
      accueil: "نعاونك تلقى مقسم صناعي، وتعرف الأسوام والأوراق والإجراءات متاع الوكالة العقارية الصناعية.",
      suggestions: ["نحب مقسم 3000 م² في بنزرت", "شنوّة الأوراق اللازمة باش نشري مقسم؟", "مناطق قريبة من ميناء صفاقس"] }),
    arq: Object.assign({}, ar, { accueilTitre: "مرحبا، أنا دليلة",
      accueil: "نعاونك تلقى قطعة أرض صناعية، وتعرف الأسعار والوثائق والإجراءات تاع الوكالة.",
      suggestions: ["حاب قطعة 3000 م² في بنزرت", "واش هي الوثائق اللازمة باش نشري قطعة؟"] }),
    ayl: Object.assign({}, ar, { accueilTitre: "مرحبا، أنا دليلة",
      accueil: "نعاونك تلقى قطعة أرض صناعية، وتعرف الأسعار والأوراق والإجراءات متاع الوكالة.",
      suggestions: ["نبي قطعة 3000 م² في بنزرت", "شن هي الأوراق اللازمة باش نشري قطعة؟"] })
  };
  var LANGUES = [["fr", "Français"], ["ar", "العربية"], ["aeb", "تونسي"], ["arq", "دزيري"], ["ayl", "ليبي"],
                 ["en", "English"], ["de", "Deutsch"], ["tr", "Türkçe"]];

  /* ------------------------------------------------------------------ icônes (traits, couleur du texte) */
  var ICONES = {
    fermer: '<path d="M6 6l12 12M18 6L6 18"/>',
    micro: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    stopMicro: '<rect x="7" y="7" width="10" height="10" rx="2"/>',
    envoyer: '<path d="M4 12l16-8-6 16-2-7-8-1z"/>',
    hautParleur: '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    pouceHaut: '<path d="M7 11v9H4v-9h3zM7 11l4-8a2 2 0 0 1 2 2v4h5a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 16.8 20H7"/>',
    pouceBas: '<path d="M7 13V4H4v9h3zM7 13l4 8a2 2 0 0 0 2-2v-4h5a2 2 0 0 0 2-2.3l-1.2-7A2 2 0 0 0 16.8 4H7"/>',
    repere: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    lot: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 12h16M12 4v16"/>',
    document: '<path d="M14 3H6v18h12V7l-4-4z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>'
  };
  function icone(nom) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-hidden="true" focusable="false">' + ICONES[nom] + "</svg>";
  }
  function anneau() {
    return '<span class="dl-anneau" aria-hidden="true"><svg viewBox="0 0 44 44">' +
      '<path class="dl-arc" d="M22 2a20 20 0 0 1 20 20"/>' +
      '<path class="dl-arc" d="M42 22a20 20 0 0 1-20 20"/>' +
      '<path class="dl-arc" d="M22 42A20 20 0 0 1 2 22"/></svg><span class="dl-visage">D</span></span>';
  }

  /* ------------------------------------------------------------------ petits outils DOM */
  function el(tag, attrs, enfants) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (attrs[k] == null || attrs[k] === false) continue;
      if (k === "texte") n.textContent = attrs[k];
      else if (k === "html") n.innerHTML = attrs[k];            // uniquement pour nos icônes
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    }
    (enfants || []).forEach(function (e) { if (e != null) n.appendChild(typeof e === "string" ? document.createTextNode(e) : e); });
    return n;
  }
  function lienSur(url) { return /^https?:\/\//i.test(url) ? url : null; }
  function idSession() {
    try { return crypto.randomUUID(); } catch (e) { return "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10); }
  }
  function memoire(cle, valeur) {
    try { if (valeur === undefined) return localStorage.getItem(cle); localStorage.setItem(cle, valeur); } catch (e) { return null; }
  }

  /* ------------------------------------------------------------------ état */
  var etat = {
    lang: null, historique: [], session: idSession(), contexte: null, occupe: false,
    enregistreur: null, morceaux: [], audio: null, boutonLecture: null, parQuestionVocale: false
  };
  var ui = {};
  function t(cle) { return (TEXTES[etat.lang] || TEXTES.fr)[cle]; }

  function langueDeDepart() {
    var l = (memoire("dalila_lang") || (script && script.getAttribute("data-lang")) ||
             document.documentElement.lang || navigator.language || "fr").toLowerCase();
    if (TEXTES[l]) return l;
    l = l.slice(0, 2);
    return TEXTES[l] ? l : "fr";
  }

  /* ------------------------------------------------------------------ appels à l'API */
  function appeler(chemin, options, delai) {
    var ctrl = new AbortController();
    var minuteur = setTimeout(function () { ctrl.abort(); }, delai || DELAI_MS);
    options = options || {};
    options.signal = ctrl.signal;
    return fetch(API + chemin, options).finally(function () { clearTimeout(minuteur); });
  }
  function json(chemin, corps, delai) {
    return appeler(chemin, { method: "POST", headers: { "Content-Type": "application/json" },
                             body: JSON.stringify(corps) }, delai);
  }

  /* ------------------------------------------------------------------ rendu d'une réponse
     Une ligne « - … » devient un élément de liste ; [[ZONE]] et [[LOT]] des boutons qui centrent la carte ;
     [[PDF]] un lien vers le document ; [[CHOIX]] un bouton sous la réponse ; une ligne faite de liens
     [titre](url) la ligne des sources. Les nombres avec unité sont mis en gras pour être lus d'abord. */
  var JETON = /\[\[(ZONE|LOT|CHOIX|PDF):([^\]]+)\]\]|\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)|\*\*([^*\n]+)\*\*/g;
  var NOMBRE = /(\d[\d   ,.]*\s?(?:DT\/m²|DT|m²|km|ha|jours?|mois)?)/g;

  function texteAvecNombres(parent, texte, enGras) {
    if (!enGras) { parent.appendChild(document.createTextNode(texte)); return; }
    var dernier = 0, m;
    NOMBRE.lastIndex = 0;
    while ((m = NOMBRE.exec(texte))) {
      var nombre = m[1].replace(/[\s,.]+$/, "");
      if (!nombre) continue;
      parent.appendChild(document.createTextNode(texte.slice(dernier, m.index)));
      parent.appendChild(el("strong", { texte: nombre }));
      dernier = m.index + nombre.length;
      NOMBRE.lastIndex = dernier;
    }
    parent.appendChild(document.createTextNode(texte.slice(dernier)));
  }

  function separer(valeur, aLaFin) {   // « id:nom » (ZONE, LOT) ou « url:libellé » (PDF, l'url contient des « : »)
    var i = aLaFin ? valeur.lastIndexOf(":") : valeur.indexOf(":");
    return i < 0 ? [valeur, valeur] : [valeur.slice(0, i), valeur.slice(i + 1)];
  }

  function signaler(type, id, nom) {
    var detail = { id: id, nom: nom };
    window.dispatchEvent(new CustomEvent("dalila:" + type, { detail: detail }));
  }

  function remplirLigne(parent, ligne, choix, liens, enGras) {
    var dernier = 0, m;
    JETON.lastIndex = 0;
    while ((m = JETON.exec(ligne))) {
      texteAvecNombres(parent, ligne.slice(dernier, m.index), enGras);
      dernier = m.index + m[0].length;
      if (m[1] === "CHOIX") { choix.push(m[2].trim()); continue; }
      if (m[1] === "ZONE") {
        var z = separer(m[2]);
        parent.appendChild(el("button", { type: "button", "class": "dl-puce", title: t("voirCarte"),
          onclick: signaler.bind(null, "zone", z[0], z[1]) }, [el("span", { html: icone("repere") }).firstChild, z[1]]));
      } else if (m[1] === "LOT") {
        var l = separer(m[2]);
        parent.appendChild(el("button", { type: "button", "class": "dl-puce dl-lot", title: t("voirCarte"),
          onclick: signaler.bind(null, "lot", l[0], l[1]) }, [el("span", { html: icone("lot") }).firstChild, t("lot") + " " + l[1]]));
      } else if (m[1] === "PDF") {
        var p = separer(m[2], true), url = lienSur(p[0]);
        if (url) liens.docs.push({ url: url, titre: p[1] });
        else parent.appendChild(document.createTextNode(p[1]));
      } else if (m[3]) {
        var u = lienSur(m[4]);
        parent.appendChild(u ? el("a", { href: u, target: "_blank", rel: "noopener noreferrer", texte: m[3] })
                             : document.createTextNode(m[3]));
      } else if (m[5]) {
        parent.appendChild(el("strong", { texte: m[5] }));
      }
    }
    texteAvecNombres(parent, ligne.slice(dernier), enGras);
  }

  function rendreReponse(texte) {
    var corps = el("div", { "class": "dl-texte", dir: "auto" });
    var choix = [], liens = { docs: [] }, liste = null, paragraphe = null;
    var lignesSources = [];
    (texte || "").split(/\r?\n/).forEach(function (brute) {
      var ligne = brute.trim();
      if (!ligne) { liste = null; paragraphe = null; return; }
      if (/^\[[^\]]+\]\(https?:/.test(ligne) && ligne.replace(/\[[^\]]+\]\(https?:\/\/[^)\s]+\)/g, "").replace(/[·\s]/g, "") === "") {
        lignesSources.push(ligne); return;                       // ligne des sources
      }
      if (/^\[\[CHOIX:[^\]]+\]\]$/.test(ligne)) { remplirLigne(el("span"), ligne, choix, liens, false); return; }
      if (/^\[\[PDF:[^\]]+\]\]$/.test(ligne)) { remplirLigne(el("span"), ligne, choix, liens, false); return; }
      if (/^[-•*]\s+/.test(ligne)) {
        if (!liste) { liste = el("ul", { "class": "dl-liste" }); corps.appendChild(liste); }
        var li = el("li");
        remplirLigne(li, ligne.replace(/^[-•*]\s+/, ""), choix, liens, true);
        liste.appendChild(li); paragraphe = null; return;
      }
      liste = null;
      if (!paragraphe) { paragraphe = el("p"); corps.appendChild(paragraphe); }
      else paragraphe.appendChild(el("br"));
      remplirLigne(paragraphe, ligne, choix, liens, false);
    });
    liens.docs.forEach(function (d) {
      corps.appendChild(el("a", { "class": "dl-doc", href: d.url, target: "_blank", rel: "noopener noreferrer" },
        [el("span", { html: icone("document") }).firstChild, d.titre]));
    });
    if (lignesSources.length) {
      var s = el("p", { "class": "dl-sources" }, [t("sources") + " "]);
      lignesSources.forEach(function (l, i) { if (i) s.appendChild(document.createTextNode(" · ")); remplirLigne(s, l, choix, liens, false); });
      corps.appendChild(s);
    }
    return { corps: corps, choix: choix };
  }

  /* ------------------------------------------------------------------ fil de la conversation */
  function defiler() { ui.fil.scrollTop = ui.fil.scrollHeight; }
  function ajouter(n) { ui.fil.appendChild(n); defiler(); return n; }
  function note(texte, erreur) { return ajouter(el("p", { "class": "dl-note" + (erreur ? " dl-erreur" : ""), texte: texte, role: erreur ? "alert" : null })); }

  function humeur(nom) {   // repos | ecoute | recherche | parle : l'anneau de Dalila change
    ["dl-ecoute", "dl-recherche", "dl-parle"].forEach(function (c) { ui.racine.classList.remove(c); });
    if (nom && nom !== "repos") ui.racine.classList.add("dl-" + nom);
  }

  function accueil() {
    // la mascotte en pied, une seule fois, sur l'accueil (concept board) ; absente si le fichier n'est pas déposé
    var image = el("img", { "class": "dl-mascotte", src: BASE + "mascotte.png", alt: "", width: "120" });
    image.addEventListener("error", function () { image.remove(); });
    var bloc = el("div", { "class": "dl-accueil" }, [image,
      el("h2", { texte: t("accueilTitre") }), el("p", { texte: t("accueil") })]);
    var choix = el("div", { "class": "dl-choix" });
    t("suggestions").forEach(function (s) {
      choix.appendChild(el("button", { type: "button", texte: s, onclick: function () { envoyer(s); } }));
    });
    bloc.appendChild(choix);
    ajouter(bloc);
  }

  function bulleVisiteur(texte) { ajouter(el("div", { "class": "dl-bulle dl-visiteur", dir: "auto", texte: texte })); }

  function bulleReponse(r, lang) {
    var rendu = rendreReponse(r.message);
    var bulle = el("div", { "class": "dl-bulle dl-reponse" + (r.source === "repli" ? " dl-repli" : ""), lang: lang }, [rendu.corps]);
    if (rendu.choix.length) {
      var zone = el("div", { "class": "dl-choix" });
      rendu.choix.forEach(function (c) {
        zone.appendChild(el("button", { type: "button", dir: "auto", texte: c, onclick: function () {
          Array.prototype.forEach.call(zone.querySelectorAll("button"), function (b) { b.disabled = true; });
          envoyer(c);
        } }));
      });
      bulle.appendChild(zone);
    }
    var actions = el("div", { "class": "dl-actions" });
    actions.appendChild(el("span", { "class": "dl-meta", texte: r.duree_s ? (Math.round(r.duree_s) + " " + t("secondes")) : "" }));
    var lecture = el("button", { type: "button", "class": "dl-icone", "aria-label": t("lire"), title: t("lire"), html: icone("hautParleur") });
    lecture.addEventListener("click", function () { lire(r.message, lang, lecture); });
    actions.appendChild(lecture);
    if (r.log_id != null) {
      var haut = el("button", { type: "button", "class": "dl-icone", "aria-label": t("utile"), title: t("utile"), "aria-pressed": "false", html: icone("pouceHaut") });
      var bas = el("button", { type: "button", "class": "dl-icone", "aria-label": t("pasUtile"), title: t("pasUtile"), "aria-pressed": "false", html: icone("pouceBas") });
      var donner = function (utile) {
        haut.setAttribute("aria-pressed", utile ? "true" : "false");
        bas.setAttribute("aria-pressed", utile ? "false" : "true");
        json("/carte/chatbot/avis", { log_id: r.log_id, utile: utile }, 15000)
          .then(function () { actions.firstChild.textContent = t("merci"); })
          .catch(function () {});
      };
      haut.addEventListener("click", function () { donner(true); });
      bas.addEventListener("click", function () { donner(false); });
      actions.appendChild(haut); actions.appendChild(bas);
    }
    bulle.appendChild(actions);
    ajouter(bulle);
    return lecture;
  }

  /* ------------------------------------------------------------------ envoyer une question */
  function envoyer(texte) {
    texte = (texte || "").trim().slice(0, TAILLE_MAX);
    if (!texte || etat.occupe) return;
    etat.occupe = true;
    ui.envoyer.disabled = true;
    ui.champ.value = ""; ajusterChamp();
    var vocale = etat.parQuestionVocale; etat.parQuestionVocale = false;
    var lang = etat.lang;
    bulleVisiteur(texte);

    var debut = Date.now();
    var compteur = el("span", { texte: "" });
    var attente = ajouter(el("div", { "class": "dl-attente", role: "status" }, [t("reflechit") + " ", compteur]));
    var tic = setInterval(function () { compteur.textContent = Math.round((Date.now() - debut) / 1000) + " " + t("secondes"); }, 1000);
    humeur("recherche");

    var corps = { message: texte, history: etat.historique.slice(-HISTORIQUE_MAX), lang: lang, session_id: etat.session };
    if (etat.contexte) corps.contexte = etat.contexte;

    json("/carte/chatbot", corps)
      .then(function (rep) { if (!rep.ok) throw new Error("HTTP " + rep.status); return rep.json(); })
      .then(function (r) {
        etat.historique.push({ role: "user", content: texte }, { role: "assistant", content: r.message });
        etat.historique = etat.historique.slice(-HISTORIQUE_MAX);
        attente.remove();
        var bouton = bulleReponse(r, lang);
        if (vocale) lire(r.message, lang, bouton);   // question posée à la voix : la réponse est lue
      })
      .catch(function (e) {
        attente.remove();
        bulleReponse({ message: e && e.name === "AbortError" ? t("delai") : t("horsService"), source: "repli", log_id: null }, lang);
      })
      .finally(function () {
        clearInterval(tic);
        etat.occupe = false; ui.envoyer.disabled = false;
        if (!etat.audio) humeur("repos");
        ui.champ.focus();
      });
  }

  /* ------------------------------------------------------------------ lecture à voix haute */
  function arreterLecture() {
    if (etat.audio) { etat.audio.pause(); etat.audio = null; }
    if (etat.boutonLecture) {
      etat.boutonLecture.innerHTML = icone("hautParleur");
      etat.boutonLecture.setAttribute("aria-label", t("lire"));
      etat.boutonLecture = null;
    }
    humeur("repos");
  }
  function lire(texte, lang, bouton) {
    if (etat.boutonLecture === bouton) { arreterLecture(); return; }
    arreterLecture();
    etat.boutonLecture = bouton;
    bouton.innerHTML = icone("stop"); bouton.setAttribute("aria-label", t("stop"));
    json("/carte/voix/lire", { texte: texte, lang: lang }, 30000)
      .then(function (rep) {
        if (rep.status !== 200) throw new Error("pas-de-voix");
        return rep.blob();
      })
      .then(function (wav) {
        if (etat.boutonLecture !== bouton) return;
        var url = URL.createObjectURL(wav);
        var audio = new Audio(url);
        etat.audio = audio;
        audio.onended = function () { URL.revokeObjectURL(url); if (etat.audio === audio) arreterLecture(); };
        humeur("parle");
        return audio.play();
      })
      .catch(function (e) {
        if (etat.boutonLecture === bouton) arreterLecture();
        if (e && e.message === "pas-de-voix") note(t("pasDeVoix"));
      });
  }

  /* ------------------------------------------------------------------ micro */
  function demanderConsentement(suite) {
    var bloc = el("div", { "class": "dl-consentement", role: "dialog", "aria-label": t("consentTitre") }, [
      el("h3", { texte: t("consentTitre") }), el("p", { texte: t("consent") })]);
    var boutons = el("div", { "class": "dl-boutons" }, [
      el("button", { type: "button", "class": "dl-principal", texte: t("autoriser"), onclick: function () {
        memoire("dalila_micro", "oui"); bloc.remove(); suite(); } }),
      el("button", { type: "button", "class": "dl-secondaire", texte: t("ecrire"), onclick: function () {
        bloc.remove(); ui.champ.focus(); } })]);
    bloc.appendChild(boutons);
    ajouter(bloc);
    boutons.firstChild.focus();
  }

  function basculerMicro() {
    if (etat.enregistreur && etat.enregistreur.state === "recording") { etat.enregistreur.stop(); return; }
    if (memoire("dalila_micro") !== "oui") { demanderConsentement(enregistrer); return; }
    enregistrer();
  }

  function enregistrer() {
    arreterLecture();
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (flux) {
      var rec = new MediaRecorder(flux);
      etat.enregistreur = rec; etat.morceaux = [];
      rec.ondataavailable = function (e) { if (e.data && e.data.size) etat.morceaux.push(e.data); };
      rec.onstop = function () {
        flux.getTracks().forEach(function (p) { p.stop(); });
        ui.micro.classList.remove("dl-actif");
        ui.micro.innerHTML = icone("micro"); ui.micro.setAttribute("aria-label", t("micro"));
        ui.etat.textContent = t("transcription");
        humeur("recherche");
        var donnees = new FormData();
        donnees.append("audio", new Blob(etat.morceaux, { type: rec.mimeType || "audio/webm" }), "question.webm");
        etat.morceaux = [];
        appeler("/carte/voix/transcrire", { method: "POST", body: donnees }, 30000)
          .then(function (rep) { return rep.json().then(function (j) { if (!rep.ok) throw new Error(j.detail || rep.status); return j; }); })
          .then(function (j) {
            ui.champ.value = (j.texte || "").trim(); ajusterChamp();
            etat.parQuestionVocale = true;
            ui.etat.textContent = t("verifier");          // le texte reconnu est vu et corrigé AVANT l'envoi
            ui.champ.focus();
          })
          .catch(function (e) { ui.etat.textContent = t("sousTitre"); note(t("microIndispo") + (e && e.message ? " (" + e.message + ")" : ""), true); })
          .finally(function () { humeur("repos"); });
      };
      rec.start();
      ui.micro.classList.add("dl-actif");
      ui.micro.innerHTML = icone("stopMicro"); ui.micro.setAttribute("aria-label", t("arreter"));
      ui.etat.textContent = t("ecoute");
      humeur("ecoute");
    }).catch(function (e) { note(t("microIndispo") + (e && e.name ? " (" + e.name + ")" : ""), true); });
  }

  /* ------------------------------------------------------------------ service prêt ? */
  function verifierService() {
    appeler("/sante", { method: "GET" }, 8000)
      .then(function (rep) { return rep.json(); })
      .then(function (s) {
        if (s.pret) { ui.avis.hidden = true; return; }
        ui.avis.textContent = t("preparation"); ui.avis.hidden = false;
        setTimeout(verifierService, 10000);
      })
      .catch(function () { ui.avis.textContent = t("horsService"); ui.avis.hidden = false; });
  }

  /* ------------------------------------------------------------------ contexte venu de la carte */
  function definirContexte(c) {
    etat.contexte = c && typeof c === "object" ? c : null;
    if (!ui.contexte) return;
    if (!etat.contexte) { ui.contexte.hidden = true; return; }
    var nom = etat.contexte.nom || etat.contexte.libelle ||
      (etat.contexte.lot != null ? t("lot") + " " + etat.contexte.lot : "") || etat.contexte.zone || etat.contexte.page || "";
    ui.contexteTexte.textContent = t("contexte") + " " + nom;
    ui.contexte.hidden = false;
  }

  /* ------------------------------------------------------------------ langue */
  function appliquerLangue(l) {
    etat.lang = TEXTES[l] ? l : "fr";
    memoire("dalila_lang", etat.lang);
    var dir = RTL[etat.lang] ? "rtl" : "ltr";
    ui.panneau.setAttribute("dir", dir);
    ui.panneau.setAttribute("lang", etat.lang === "aeb" || etat.lang === "arq" || etat.lang === "ayl" ? "ar" : etat.lang);
    ui.nom.textContent = t("nom");
    ui.etat.textContent = t("sousTitre");
    ui.lanceurTexte.textContent = t("ouvrir");
    ui.fermer.setAttribute("aria-label", t("fermer"));
    ui.choixLangue.setAttribute("aria-label", t("langue"));
    ui.etiquette.textContent = t("saisie");
    ui.champ.placeholder = t("placeholder");
    ui.envoyer.setAttribute("aria-label", t("envoyer")); ui.envoyer.title = t("envoyer");
    ui.micro.setAttribute("aria-label", t("micro")); ui.micro.title = t("micro");
    ui.retirer.setAttribute("aria-label", t("retirer"));
    ui.pied.textContent = t("pied");
    definirContexte(etat.contexte);
  }

  function ajusterChamp() {
    ui.champ.style.height = "auto";
    ui.champ.style.height = Math.min(ui.champ.scrollHeight, 140) + "px";
    ui.champ.style.overflowY = ui.champ.scrollHeight > 140 ? "auto" : "hidden";
  }

  /* ------------------------------------------------------------------ construction */
  function chargerStyle() {
    if (document.querySelector("link[data-dalila]")) return;
    document.head.appendChild(el("link", { rel: "stylesheet", href: BASE + "dalila.css", "data-dalila": "1" }));
    document.head.appendChild(el("link", { rel: "stylesheet", "data-dalila": "2",
      href: "https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@400;700&display=swap" }));
  }

  function construire() {
    chargerStyle();
    ui.racine = el("div", { "class": "dl-racine" });
    ui.lanceurTexte = el("span");
    ui.lanceur = el("button", { type: "button", "class": "dl-lanceur", "aria-haspopup": "dialog", onclick: ouvrir });
    ui.lanceur.innerHTML = anneau(); ui.lanceur.appendChild(ui.lanceurTexte);

    ui.nom = el("p", { "class": "dl-nom" });
    ui.etat = el("p", { "class": "dl-etat", "aria-live": "polite" });
    ui.choixLangue = el("select", { "class": "dl-langue" });
    LANGUES.forEach(function (l) { ui.choixLangue.appendChild(el("option", { value: l[0], texte: l[1] })); });
    ui.choixLangue.addEventListener("change", function () { appliquerLangue(ui.choixLangue.value); });
    ui.fermer = el("button", { type: "button", "class": "dl-icone", html: icone("fermer"), onclick: fermer });
    var avatar = el("span"); avatar.innerHTML = anneau();
    var entete = el("div", { "class": "dl-entete" }, [avatar.firstChild,
      el("div", { "class": "dl-titre" }, [ui.nom, ui.etat]), ui.choixLangue, ui.fermer]);

    ui.avis = el("p", { "class": "dl-avis-service", role: "status", hidden: true });
    ui.fil = el("div", { "class": "dl-fil", "aria-live": "polite" });

    ui.contexteTexte = el("span");
    ui.retirer = el("button", { type: "button", "class": "dl-icone", html: icone("fermer"), onclick: function () { definirContexte(null); } });
    ui.contexte = el("p", { "class": "dl-contexte", hidden: true }, [ui.contexteTexte, ui.retirer]);

    ui.etiquette = el("label", { "for": "dl-champ" });
    ui.champ = el("textarea", { id: "dl-champ", rows: "1", maxlength: String(TAILLE_MAX), dir: "auto" });
    ui.champ.addEventListener("input", ajusterChamp);
    ui.champ.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); envoyer(ui.champ.value); }
    });
    ui.micro = el("button", { type: "button", "class": "dl-icone dl-micro", html: icone("micro"), onclick: basculerMicro });
    if (!(navigator.mediaDevices && window.MediaRecorder)) ui.micro.hidden = true;  // micro : HTTPS ou localhost
    ui.envoyer = el("button", { type: "button", "class": "dl-principal", html: icone("envoyer"), onclick: function () { envoyer(ui.champ.value); } });
    var saisie = el("div", { "class": "dl-saisie" }, [ui.etiquette, ui.champ, ui.micro, ui.envoyer]);
    ui.pied = el("p", { "class": "dl-pied" });

    ui.panneau = el("section", { "class": "dl-panneau", role: "dialog", "aria-label": "Dalila" },
      [entete, ui.avis, ui.fil, ui.contexte, saisie, ui.pied]);
    ui.panneau.addEventListener("keydown", function (e) { if (e.key === "Escape") fermer(); });

    ui.racine.appendChild(ui.lanceur);
    ui.racine.appendChild(ui.panneau);
    document.body.appendChild(ui.racine);

    var l = langueDeDepart();
    ui.choixLangue.value = l;
    appliquerLangue(l);
  }

  var dejaOuvert = false;
  function ouvrir() {
    ui.racine.classList.add("dl-ouvert");
    if (!dejaOuvert) { dejaOuvert = true; accueil(); }
    verifierService();
    ui.champ.focus();
  }
  function fermer() {
    if (etat.enregistreur && etat.enregistreur.state === "recording") etat.enregistreur.stop();
    arreterLecture();
    ui.racine.classList.remove("dl-ouvert");
    ui.lanceur.focus();
  }

  /* ------------------------------------------------------------------ ce que la carte peut appeler */
  window.Dalila = {
    ouvrir: function () { ouvrir(); },
    fermer: function () { fermer(); },
    demander: function (texte, contexte) { if (contexte !== undefined) definirContexte(contexte); ouvrir(); envoyer(texte); },
    definirContexte: function (c) { definirContexte(c); },
    langue: function (l) { if (l) { ui.choixLangue.value = TEXTES[l] ? l : "fr"; appliquerLangue(l); } return etat.lang; },
    _rendre: rendreReponse   // pour les tests
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", construire);
  else construire();
})();
