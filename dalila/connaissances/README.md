# Construction de la base de connaissances

Construit et met à jour tout ce que l'agent lit : tables et vues MariaDB, corrections, passages et vecteurs, graphe.

| | |
|---|---|
| **Exigences** | BNF1, BF16, BNF19 |
| **Contrat** | Ordre : migrer → charger → construire_abox → vectoriser ; rafraichir_copie_afi pour remettre la copie AFI à jour ; lire_carte_afi et extraire_corrections pour revoir les décisions sur les données ; preparer_corpus une seule fois. |
| **S'appuie sur** | db/, ontology/, donnees/ (hors git) |
| **État** | Existant. |
