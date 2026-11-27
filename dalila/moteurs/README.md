# Module moteurs

Moteur de langage local Ollama (`moteurs/llm.py`) et embeddings de recherche configurables (`moteurs/embeddings.py`).
Le reranker est optionnel; le moteur vocal n'est pas implémenté.

| | |
|---|---|
| **Exigences** | BNF10, BNF12, BNF9 |
| **Contrat** | Modèles locaux uniquement, aucune clé ni service externe ; le serveur de l'AFI n'a pas de carte graphique (8 vCPU, 16 Go) : chaque modèle est mesuré sur processeur. Licence et coût de chaque modèle déclarés (livrables). |
| **S'appuie sur** | — |
| **État** | Ollama et les embeddings sont implémentés. E5 est le défaut léger; BGE-M3 et Qwen3 sont des choix explicites. Le chargement de modèle et l'intégration complète doivent encore être validés sur l'environnement de déploiement. |
