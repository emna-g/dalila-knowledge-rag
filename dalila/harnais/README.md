# Harnais de l'agent

La boucle d'agent et ses garde-fous : entrée, injection d'instructions, outils bornés, ancrage de la réponse dans les faits, règles métier, repli. Voir docs/decisions.md, « Le harnais de l'agent ».

| | |
|---|---|
| **Exigences** | BF4, BF6, BF10, BF11, BF22, BF24, BNF1, BNF2, BNF4, BNF9, BNF13, BNF14, VI.4 |
| **Contrat** | Entrée : question normalisée (module langue) et contexte. Sortie : réponse ancrée (chaque chiffre et chaque balise viennent d'un outil), avec ses sources. |
| **S'appuie sur** | langue, semantique, traitement, sources, moteurs |
| **État** | `agent.py` implémente la boucle Ollama/outils, les bornes, le contrôle d'ancrage et le repli. L'intégration réelle complète avec MariaDB, le corpus vectorisé et Ollama doit encore être validée sur une base de test. `pipeline_fixe.py` reste l'ancienne chaîne utilisée par `scripts/tester.py` et `eval/run_eval.py`; ces commandes n'évaluent pas le nouvel agent. |
