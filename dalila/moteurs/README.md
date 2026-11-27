# Module moteurs

Adaptateurs interchangeables par configuration : modèle de langage local (Ollama), modèle de recherche (embeddings), reranker, voix.

| | |
|---|---|
| **Exigences** | BNF10, BNF12, BNF9 |
| **Contrat** | Modèles locaux uniquement, aucune clé ni service externe ; le serveur de l'AFI n'a pas de carte graphique (8 vCPU, 16 Go) : chaque modèle est mesuré sur processeur. Licence et coût de chaque modèle déclarés (livrables). |
| **S'appuie sur** | — |
| **État** | À faire (le chargement des modèles de recherche est aujourd'hui dans semantique/recherche.py). |
