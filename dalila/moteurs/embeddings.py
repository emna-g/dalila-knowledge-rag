"""Modèle de recherche (embeddings), chargé une seule fois et partagé par tous les modules.

    from dalila.moteurs.embeddings import encoder_questions, encoder_textes
    encoder_questions(["lot près du port"])      # vecteurs normalisés, avec le préfixe de question du modèle
    encoder_textes(["Pêche et aquaculture"])     # avec le préfixe de passage du modèle

Le modèle est celui de la configuration (DALILA_MODELE, E5 multilingue léger par défaut, local). Carte graphique si
elle est là, processeur sinon. BGE-M3 et Qwen3 sont des choix explicites après validation sur échantillon.
"""
from functools import lru_cache
from dalila.config import MODELE, MODELES_RECHERCHE


@lru_cache(maxsize=None)
def modele(nom=MODELE):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODELES_RECHERCHE[nom]["nom"], device=None)


def encoder_questions(textes, nom=MODELE):
    cfg = MODELES_RECHERCHE[nom]
    return modele(nom).encode([cfg["prefixe_question"] + t for t in textes], normalize_embeddings=True)


def encoder_textes(textes, nom=MODELE):
    cfg = MODELES_RECHERCHE[nom]
    return modele(nom).encode([cfg["prefixe_passage"] + t for t in textes], normalize_embeddings=True, batch_size=32)
