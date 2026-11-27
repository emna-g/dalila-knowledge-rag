# Harnais de l'agent

La boucle d'agent et ses garde-fous : entrée, injection d'instructions, outils bornés, ancrage de la réponse dans les faits, règles métier, repli. Voir docs/decisions.md, « Le harnais de l'agent ».

| | |
|---|---|
| **Exigences** | BF4, BF6, BF10, BF11, BF22, BF24, BNF1, BNF2, BNF4, BNF9, BNF13, BNF14, VI.4 |
| **Contrat** | Entrée : question normalisée (module langue) et contexte. Sortie : réponse ancrée (chaque chiffre et chaque balise viennent d'un outil), avec ses sources. |
| **S'appuie sur** | langue, semantique, traitement, sources, moteurs |
| **État** | À faire. `pipeline_fixe.py` est l'ancienne chaîne fixe (graphe → chiffres → passages), gardée pour `scripts/tester.py` et `eval/run_eval.py` jusqu'à ce que la boucle d'agent la remplace. |
