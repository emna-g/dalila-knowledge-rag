"""Assemble les briques pour une question : graphe (comprendre) -> base (chiffres) -> passages (recherche).
C'est exactement ce que le LLM recevrait pour rédiger la réponse (le LLM n'est pas encore branché).

    from dalila.harnais.pipeline_fixe import Dalila
    d = Dalila()
    d.analyser("quels sont les comodités prés de la zone industrielle sidi achour borj el amri")
"""
from dalila.semantique.comprendre import Comprendre
from dalila.traitement.outils import Outils
from dalila.semantique.recherche import Recherche
from dalila.config import MODELE, RERANKER


class Dalila:
    def __init__(self, modele=MODELE, reranker=RERANKER, echantillon=False):
        self.comprendre = Comprendre()
        self.outils = Outils()
        self.recherche = Recherche(modele=modele, reranker=reranker, echantillon=echantillon)

    def analyser(self, question, k=5):
        sens = self.comprendre.analyser(question)
        zone_ids = [z for z, _ in sens["zones"]]
        regime = None
        chiffres = {}
        if zone_ids:
            chiffres["zones"] = [self.outils.fiche_zone(z) for z in zone_ids[:3]]
            regs = {z["zone_developpement_regional"] for z in chiffres["zones"] if z}
            regime = {frozenset({1}): "developpement_regional", frozenset({0}): "littoral"}.get(frozenset(regs))
            if sens["intention"] == "lots":
                chiffres["lots"] = self.outils.chercher_lots(zone_id=zone_ids[0], limite=10)  # liste à afficher
                chiffres["nb_lots_disponibles"] = self.outils.compter_lots(zone_id=zone_ids[0])  # le vrai nombre
        elif sens["gouvernorats"]:
            g = sens["gouvernorats"][0]
            chiffres["lots"] = self.outils.chercher_lots(gouvernorat=g, limite=10)
            chiffres["nb_lots_disponibles"] = self.outils.compter_lots(gouvernorat=g)
            regime = self.outils.regime_gouvernorat(g)
        res = self.recherche.chercher(question, k=k, zone_ids=zone_ids or None, regime=regime,
                                      fiches_afi=set(sens["fiches_afi"]) or None, demarche=sens["intention"] == "demarche")
        return {"question": question, "sens": sens, "regime": regime, "chiffres": chiffres, **res}
