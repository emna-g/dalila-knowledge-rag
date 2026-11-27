# Module moteurs

Adaptateurs interchangeables par configuration : modèle de langage local (Ollama), modèle de recherche (embeddings), reranker, voix.

| | |
|---|---|
| **Exigences** | BNF10, BNF12, BNF9 |
| **Contrat** | Modèles locaux uniquement, aucune clé ni service externe ; le serveur de l'AFI n'a pas de carte graphique (8 vCPU, 16 Go) : chaque modèle est mesuré sur processeur. Licence et coût de chaque modèle déclarés (livrables). |
| **S'appuie sur** | — |
| **État** | Partiel : `llm.py` (Ollama, appels d'outils, arrêt en flux, processeur seul par `DALILA_LLM_CPU`) ; modèles de recherche dans semantique/recherche.py, de voix dans dalila/voix. |
