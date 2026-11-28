# Module langue

Détecte la langue et l'écriture (6 langues : fr, en, ar, de, tr, tunisien ; arabizi, mélange avec le français ; algérien et libyen abandonnés le 2026-11-28, rendus comme tunisien), ramène la question à une forme comprise, reformule la réponse dans la langue du visiteur sans changer chiffres ni balises.

| | |
|---|---|
| **Exigences** | BF1, BF2, BF3, BF5, BNF5, BNF13 |
| **Contrat** | Par un modèle local (aucune règle écrite à la main pour les langues). `lexique/` : lexique tunisien attesté, gardé comme ressource et pour les tests ; il sortira du chemin des réponses. |
| **S'appuie sur** | moteurs |
| **État** | Fait : détection de la langue par modèles (`detection.py`, `entrainer_detection.py`), 18/18 sur le jeu des 6 langues, 25/26 sur le tunisien du lexique ; les anciennes règles (lexique, mots vides) sont coupées sur le chemin du service et gardées pour l'ancienne chaîne fixe et la comparaison mesurée. |
