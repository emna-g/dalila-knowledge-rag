# Construction de la base de connaissances

Construit et met à jour tout ce que l'agent lit : tables et vues MariaDB, corrections, passages et vecteurs, graphe.

| | |
|---|---|
| **Exigences** | BNF1, BF16, BNF19 |
| **Contrat** | Base existante : migration ciblée validée → charger avec `dalila_ingest` → construire_abox en lecture seule. La synchronisation est upsert-only; les surfaces KML nécessitent `--surfaces`. Vectorisation séparée : créer l'échantillon, indexer E5 avec `--echantillon`, évaluer, puis seulement autoriser `--index-complet`. `charger` n'exécute aucune migration et n'efface rien par défaut. `rafraichir_copie_afi` met à jour la copie AFI ; `preparer_corpus` se lance une fois. |
| **S'appuie sur** | db/, ontology/, donnees/ (hors git) |
| **État** | Existant. |
