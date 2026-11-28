"""L'agent Dalila : un modèle local qui choisit ses outils (RAG agentique), entouré d'un harnais.

    from dalila.harnais.agent import Agent
    Agent().repondre("lot de 2000 m² à Jendouba", historique=[], lang="fr", contexte=None)
    -> {"reponse", "texte_modele", "source", "outils", "ancrage", "etapes", "duree_s", "modele", "erreur"}

Boucle : le modèle lit la question -> appelle des outils du registre (liste fermée, arguments validés, lecture seule)
-> lit une vue courte de leurs résultats -> recommence ou répond. Bornes : nombre d'étapes, d'appels par étape, jetons
écrits et délai total (BNF2 : 35 s).

Le harnais fait ce qu'un petit modèle sur processeur fait lentement ou mal (mesures : docs/decisions.md) :
- à la première étape, un outil est obligatoire : si le modèle commence à écrire sans données, il est arrêté aussitôt
  et invité à appeler un outil (une seule fois : une question hors sujet reçoit alors une réponse sans outil) ;
- les listes (lots, zones), balises, documents et sources sont écrits par le harnais à partir des résultats d'outils
  (vues.bloc) et ajoutés sous les phrases du modèle, qui reste court ;
- la réponse du modèle passe la vérification d'ancrage (garde_fous) ; en cas d'échec il est relancé une fois avec la
  liste de ce qui n'est pas justifié, puis le harnais répond par le repli, suivi des faits trouvés s'il y en a.
"""
import json, re, time
from dalila.harnais.consignes import RAPPEL_BOUCLE, RAPPEL_LANGUE, RAPPEL_OUTIL, REPLI, note_contexte, systeme
from dalila.harnais.garde_fous import nettoyer_entree, verifier_ancrage
from dalila.harnais.vues import bloc, vue
from dalila.moteurs.llm import MODELE_LLM, ErreurMoteur, discuter
from dalila.traitement.registre import appeler, definitions

JETONS_ETAPE = 130          # un appel d'outil fait 20 à 50 jetons ; une réponse 60 mots au plus
JETONS_MIN = 50             # de quoi écrire un appel d'outil
JETONS_PAR_S = 4.0          # écriture mesurée sur processeur 8 fils (4,5 à 6 jetons/s) : valeur prudente
CARACTERES_LUS_PAR_S = 200  # lecture de texte nouveau (≈ 70 jetons/s, 3 caractères par jeton)
RAPPELS_MAX = 2


def _jetons(reste, a_lire):
    """Borne d'écriture tirée du temps qui reste, une fois lus les a_lire caractères nouveaux : la réponse finit,
    phrases complètes, avant le délai (BNF2), au lieu d'être coupée par lui et remplacée par le repli."""
    lecture = 1.0 + a_lire / CARACTERES_LUS_PAR_S
    return max(JETONS_MIN, min(JETONS_ETAPE, int((reste - lecture) * JETONS_PAR_S)))


HORS_SUJET = {"type": "function", "function": {
    "name": "hors_sujet",
    "description": "À appeler quand le message ne concerne ni l'AFI, ni ses zones et lots, ni l'investissement "
                   "industriel en Tunisie (cuisine, politique, données personnelles, création de compte...), ou n'est "
                   "qu'une salutation ou un remerciement. Toute question sur l'AFI elle-même n'est pas hors sujet.",
    "parameters": {"type": "object", "properties": {}}}}
ETUDE = {"type": "function", "function": {
    "name": "etude_de_projet",
    "description": "Commencer l'étude de projet guidée : 10 questions, puis une étude en PDF. À appeler quand le "
                   "visiteur demande une étude, un dossier, un plan ou un rapport sur son projet.",
    "parameters": {"type": "object", "properties": {}}}}
CONSIGNE_HORS_SUJET = {"hors_sujet": True, "consigne": "Réponds poliment, sans aucune donnée : pour une salutation, "
                       "salue ; sinon dis que tu ne peux pas aider pour cela. Rappelle en une phrase ce que tu sais faire "
                       "(lots et zones industrielles, démarches de l'AFI, incitations, organismes d'investissement)."}
# résolus à l'intérieur des outils : resoudre_lieu par ceux qui prennent un nom de lieu (une étape de moins) ;
# relier_concepts, que le modèle appelait sans enchaîner ensuite (le graphe sert par conseiller)
OUTILS_CACHES = {"resoudre_lieu", "relier_concepts"}
FIN_PHRASE = re.compile(r"[.!?؟…\n](?=[^.!?؟…\n]*$)")


def _phrases_completes(texte):
    """Coupée par la borne de jetons, la réponse garde ses phrases complètes."""
    m = FIN_PHRASE.search(texte)
    if m:
        return texte[:m.end()].strip()
    return texte.rsplit(" ", 1)[0].rstrip("،,;:") + "…"  # aucune fin de phrase : au moins pas de mot coupé


LANGUES = {"fr": "français", "en": "anglais", "ar": "arabe", "de": "allemand", "tr": "turc",
           "aeb": "tunisien", "tn": "tunisien"}  # codes du contrat /carte/chatbot (champ lang) ; algérien et libyen abandonnés
DIALECTES = {"aeb", "tn"}  # code du contrat (tn) et ISO


def degenere(texte, n=3, fois=3):
    """Réponse qui boucle (le modèle répète la même suite de mots, vu en tunisien écrit en arabe) : jamais montrée."""
    mots = texte.split()
    suites = [tuple(mots[i:i + n]) for i in range(len(mots) - n + 1)]
    return any(suites.count(s) >= fois for s in set(suites))


def _lieu_inconnu(res):
    """Le lieu passé à l'outil n'a rien donné : ni lieu retenu, ni lieu à proposer."""
    return isinstance(res, dict) and "erreur" not in res and not res.get("lieux_a_proposer") and         res.get("nombre_total", res.get("nombre", 0)) is None


def appeler_avec_lieu(nom, arguments, message):
    """Le modèle réécrit parfois le lieu (« القصرين » -> « Qassrin ») ou met autre chose qu'un lieu (« port ») : un lieu
    inconnu ne doit jamais devenir « aucune zone ». Le lieu est alors cherché dans le message du visiteur lui-même ;
    si le message ne nomme aucun lieu connu, le champ lieu n'était pas un lieu et la recherche se fait sans lui.
    -> (résultat, arguments réellement utilisés)"""
    if (arguments or {}).get("lieu") and not appeler("resoudre_lieu", {"texte": message[:100]}).get("lieux"):
        arguments = {k: v for k, v in arguments.items() if k != "lieu"}  # aucun lieu dans le message : lieu inventé
    res = appeler(nom, arguments)
    if "lieu" not in (arguments or {}) or not _lieu_inconnu(res):
        return res, arguments
    for essai in ({**arguments, "lieu": message[:100]}, {k: v for k, v in arguments.items() if k != "lieu"}):
        res2 = appeler(nom, essai)
        if not _lieu_inconnu(res2):
            return res2, essai
    return res, arguments


def _langue(texte):
    """Langue détectée du message (dalila/langue/detection.py) ; modèles absents : rien, le service continue."""
    try:
        from dalila.langue.detection import detecter
        return detecter(texte)
    except Exception:  # noqa: BLE001
        return {}


def journal_outils(journal):
    """Vrai dès qu'un outil (hors rappels) a été appelé pendant la question."""
    return any(not j["outil"].startswith("(") for j in journal)


class Agent:
    def __init__(self, modele=None, delai_s=35.0, etapes_max=6, appels_par_etape=4):
        self.modele = modele or MODELE_LLM
        self.delai_s, self.etapes_max, self.appels_par_etape = delai_s, etapes_max, appels_par_etape
        self.outils = [d for d in definitions() if d["function"]["name"] not in OUTILS_CACHES] + [HORS_SUJET, ETUDE]

    def prechauffer(self):
        """Au démarrage du service : charge le modèle de recherche (BGE-M3) et le modèle de langue, et fait lire une
        fois les consignes et les outils (≈ 3 500 jetons, 40 s sur processeur) : Ollama garde cette lecture en cache,
        les questions des visiteurs ne la paient plus."""
        from dalila.moteurs.embeddings import encoder_questions
        encoder_questions(["préchauffage"])
        _langue("préchauffage")
        __import__("dalila.harnais.garde_fous", fromlist=["anonymiser"]).anonymiser("Bonjour Sami")  # noms (BNF16)
        appeler("conseiller", {"secteur": "préchauffage", "lieu": "Sfax"})  # index des activités, recherche de passages
        try:
            discuter([systeme(), {"role": "user", "content": "Bonjour"}], outils=self.outils, modele=self.modele,
                     delai_s=300, jetons_max=1)
        except ErreurMoteur:
            pass

    def repondre(self, message, historique=(), lang=None, contexte=None):
        debut = time.time()
        fin = debut + self.delai_s
        message, historique = nettoyer_entree(message, historique)
        messages = [systeme(), *historique, {"role": "user", "content": message + note_contexte(contexte)}]
        journal, resultats, deja = [], [], {}
        relance, rappels, a_lire = False, 0, 0

        detectee = _langue(message)  # BF1 : langue et écriture du message (modèles, aucune règle)

        def sortie(texte, source, ancrage=None, etape=0, erreur=None, texte_modele=None):
            return {"reponse": texte, "texte_modele": texte_modele, "source": source, "outils": journal,
                    "ancrage": ancrage, "etapes": etape, "duree_s": round(time.time() - debut, 2),
                    "modele": self.modele, "erreur": erreur, "langue_detectee": detectee}

        code = (detectee.get("langue") or lang or "").strip().lower()  # le repli dans la langue du visiteur
        repli = REPLI.get(code) or REPLI.get(code[:2]) or (REPLI["ar"] if code in DIALECTES else REPLI["fr"])
        rappel_langue = {"role": "user", "content": RAPPEL_LANGUE.format(
            message=message[:200], interface="")}  # la langue du message prime : jamais celle de l'interface

        def sortie_repli(etape, erreur, ancrage=None):
            faits = bloc(resultats)  # ce que les outils ont trouvé reste exact, même si la phrase du modèle ne l'est pas
            return sortie(repli + ("\n\n" + faits if faits else ""), "repli", ancrage, etape, erreur)

        if not message:
            return sortie(repli, "repli", erreur="message vide")

        for etape in range(1, self.etapes_max + 1):
            reste = fin - time.time()
            if reste < 1:
                return sortie_repli(etape, "délai dépassé")
            try:
                # avant d'écrire, après des résultats en français : rappel de la langue du visiteur, non gardé
                r = discuter(messages + ([rappel_langue] if journal_outils(journal) else []), outils=self.outils, modele=self.modele, delai_s=reste,
                             jetons_max=_jetons(reste, a_lire), arret_si_texte=not journal_outils(journal)
                             and rappels < RAPPELS_MAX, reponse_attendue=journal_outils(journal))
                a_lire = 0
            except ErreurMoteur as ex:
                return sortie_repli(etape, str(ex))

            if r["interrompu"]:  # réponse commencée sans aucune donnée : un outil d'abord
                rappels += 1
                journal.append({"etape": etape, "outil": "(rappel : outil d'abord)", "arguments": {}, "erreur": None,
                                "duree_s": 0, "duree_modele_s": r["duree_s"]})
                messages.append({"role": "user", "content": RAPPEL_OUTIL})
                continue

            if r["tool_calls"]:
                appels = r["tool_calls"][:self.appels_par_etape]
                messages.append({"role": "assistant", "content": r["content"],
                                 "tool_calls": [{"function": {"name": c["nom"], "arguments": c["arguments"]}}
                                                for c in appels]})
                for c in appels:
                    cle = c["nom"] + json.dumps(c["arguments"], sort_keys=True, ensure_ascii=False)
                    t = time.time()
                    if c["nom"] == "etude_de_projet":  # l'entretien est mené par le code (API, traitement/etude.py)
                        journal.append({"etape": etape, "outil": c["nom"], "arguments": {}, "erreur": None, "duree_s": 0,
                                        "duree_modele_s": r["duree_s"]})
                        return sortie("", "etude_demandee", etape=etape)
                    if c["nom"] == "hors_sujet":
                        res = CONSIGNE_HORS_SUJET
                    elif cle in deja:
                        res = deja[cle]
                    elif c["nom"] in OUTILS_CACHES:
                        res = {"erreur": f"outil inconnu : {c['nom']}"}
                    else:
                        modele_args = dict(c["arguments"])
                        res, c["arguments"] = appeler_avec_lieu(c["nom"], c["arguments"], message)
                        if modele_args != c["arguments"]:
                            c["arguments_modele"] = modele_args  # lieu inconnu remplacé : gardé pour l'apprentissage
                    if cle not in deja and c["nom"] != "hors_sujet":
                        resultats.append((c["nom"], res))
                    deja[cle] = res
                    journal.append({"etape": etape, "outil": c["nom"], "arguments": c["arguments"],
                                    "arguments_modele": c.get("arguments_modele"),
                                    "erreur": res.get("erreur"), "duree_s": round(time.time() - t, 2),
                                    "duree_modele_s": r["duree_s"]})
                    contenu = vue(c["nom"], res)
                    a_lire += len(contenu)
                    messages.append({"role": "tool", "tool_name": c["nom"], "content": contenu})
                continue

            texte = r["content"].strip()
            if r["fin"] == "length":
                texte = _phrases_completes(texte)
            if texte.strip("`'\" ") in {d["function"]["name"] for d in self.outils}:
                texte = ""  # le modèle a écrit le nom d'un outil au lieu de l'appeler : relancé comme non ancré
            ancrage = verifier_ancrage(texte, [res for _, res in resultats], message)
            boucle = degenere(texte)
            if ancrage["ok"] and texte and not boucle:
                faits = bloc(resultats)
                return sortie(texte + ("\n\n" + faits if faits else ""), "dalila", ancrage, etape,
                              texte_modele=texte)
            if relance:
                return sortie_repli(etape, "réponse qui se répète" if boucle else "réponse non ancrée", ancrage)
            relance = True
            messages.append({"role": "assistant", "content": texte})
            messages.append({"role": "user", "content": RAPPEL_BOUCLE if boucle else
                             "[Vérification automatique] Ces éléments de ta réponse ne viennent d'aucun résultat d'outil : "
                             f"nombres {ancrage['nombres_inconnus']}, balises {ancrage['balises_inconnues']}. "
                             "Appelle l'outil nécessaire, ou réécris la réponse sans ces éléments, dans la langue du visiteur."})
        return sortie_repli(self.etapes_max, "trop d'étapes")
