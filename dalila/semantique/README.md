# Module sémantique

Relie la question aux concepts de l'ontologie, interroge le graphe en SPARQL et cherche les passages par le sens.

| | |
|---|---|
| **Exigences** | BF16, BF17, BF20 |
| **Contrat** | `comprendre.py` : question → zones, gouvernorats, concepts. `recherche.py` : passages (sens + mots-clés) dans MariaDB. |
| **S'appuie sur** | ontology/ (graphe Oxigraph), base MariaDB (dalila_passages et vecteurs), moteurs |
| **État** | Existant ; le choix du modèle de recherche est dans docs/decisions.md. |
