"""L'agent Dalila : un modèle local qui choisit ses outils (RAG agentique), entouré d'un harnais.

    from dalila.harnais.agent import Agent
    Agent().repondre("lot de 2000 m² à Jendouba", historique=[], lang="fr", contexte=None)
    -> {"reponse", "source", "outils", "ancrage", "etapes", "duree_s", "modele"}

Boucle : le modèle lit la question -> appelle des outils du registre (liste fermée, arguments validés, lecture seule)
-> lit leurs résultats -> recommence ou répond. Bornes : nombre d'étapes, d'appels par étape et délai total (BNF2 : 35 s).
La réponse finale passe la vérification d'ancrage (garde_fous) ; en cas d'échec le modèle est relancé une fois avec
la liste de ce qui n'est pas justifié, puis le harnais répond par le repli. Le moteur arrêté donne aussi le repli.
"""
import json, time
from dalila.harnais.consignes import REPLI, systeme
from dalila.harnais.garde_fous import nettoyer_entree, verifier_ancrage
from dalila.moteurs.llm import MODELE_LLM, ErreurMoteur, discuter
from dalila.traitement.registre import appeler, definitions

TAILLE_RESULTAT = 6000  # caractères d'un résultat d'outil rendus au modèle (le contexte du modèle est limité)


def _sans_vides(v):
    """Retire les champs vides (None, listes et dicts vides) : rien à lire pour le modèle, du temps en moins sur
    processeur. Les zéros et les faux restent (ce sont des informations)."""
    if isinstance(v, dict):
        return {k: _sans_vides(x) for k, x in v.items() if x is not None and x != [] and x != {}}
    if isinstance(v, list):
        return [_sans_vides(x) for x in v]
    return v


def _compact(res):
    texte = json.dumps(_sans_vides(res), ensure_ascii=False, separators=(",", ":"))
    return texte if len(texte) <= TAILLE_RESULTAT else texte[:TAILLE_RESULTAT] + "…(tronqué)"


class Agent:
    def __init__(self, modele=None, delai_s=35.0, etapes_max=6, appels_par_etape=4):
        self.modele = modele or MODELE_LLM
        self.delai_s, self.etapes_max, self.appels_par_etape = delai_s, etapes_max, appels_par_etape
        self.outils = definitions()

    def prechauffer(self):
        """Au démarrage du service : charge le modèle de recherche (BGE-M3) et le modèle de langue en mémoire, pour
        que la première question d'un visiteur ne paie pas le chargement."""
        from dalila.moteurs.embeddings import encoder_questions
        encoder_questions(["préchauffage"])
        try:
            discuter([{"role": "user", "content": "Bonjour"}], modele=self.modele, delai_s=300)
        except ErreurMoteur:
            pass

    def repondre(self, message, historique=(), lang=None, contexte=None):
        debut = time.time()
        fin = debut + self.delai_s
        message, historique = nettoyer_entree(message, historique)
        messages = [systeme(contexte), *historique, {"role": "user", "content": message}]
        journal, resultats, deja = [], [], {}
        relance = False

        def sortie(texte, source, ancrage=None, etape=0, erreur=None):
            return {"reponse": texte, "source": source, "outils": journal, "ancrage": ancrage, "etapes": etape,
                    "duree_s": round(time.time() - debut, 2), "modele": self.modele, "erreur": erreur}

        repli = REPLI.get(lang or "fr", REPLI["fr"])
        if not message:
            return sortie(repli, "repli", erreur="message vide")

        for etape in range(1, self.etapes_max + 1):
            reste = fin - time.time()
            if reste < 1:
                return sortie(repli, "repli", etape=etape, erreur="délai dépassé")
            try:
                r = discuter(messages, outils=self.outils, modele=self.modele, delai_s=reste)
            except ErreurMoteur as ex:
                return sortie(repli, "repli", etape=etape, erreur=str(ex))

            if r["tool_calls"]:
                messages.append({"role": "assistant", "content": r["content"],
                                 "tool_calls": [{"function": {"name": c["nom"], "arguments": c["arguments"]}}
                                                for c in r["tool_calls"][:self.appels_par_etape]]})
                for c in r["tool_calls"][:self.appels_par_etape]:
                    cle = c["nom"] + json.dumps(c["arguments"], sort_keys=True, ensure_ascii=False)
                    t = time.time()
                    res = deja[cle] if cle in deja else appeler(c["nom"], c["arguments"])
                    deja[cle] = res
                    resultats.append(res)
                    journal.append({"etape": etape, "outil": c["nom"], "arguments": c["arguments"],
                                    "erreur": res.get("erreur"), "duree_s": round(time.time() - t, 2),
                                    "duree_modele_s": r["duree_s"]})
                    messages.append({"role": "tool", "tool_name": c["nom"], "content": _compact(res)})
                continue

            texte = r["content"].strip()
            ancrage = verifier_ancrage(texte, resultats, message)
            if ancrage["ok"] and texte:
                return sortie(texte, "dalila", ancrage, etape)
            if relance:
                return sortie(repli, "repli", ancrage, etape, erreur="réponse non ancrée")
            relance = True
            messages.append({"role": "assistant", "content": texte})
            messages.append({"role": "user", "content":
                             "[Vérification automatique] Ces éléments de ta réponse ne viennent d'aucun résultat d'outil : "
                             f"nombres {ancrage['nombres_inconnus']}, balises {ancrage['balises_inconnues']}. "
                             "Appelle l'outil nécessaire, ou réécris la réponse sans ces éléments, dans la langue du visiteur."})
        return sortie(repli, "repli", etape=self.etapes_max, erreur="trop d'étapes")
