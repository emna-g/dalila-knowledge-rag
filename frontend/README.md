# Interface

La carte interactive et la fenêtre de Dalila (8 langues, droite à gauche en arabe, micro et lecture vocale, boutons de choix, zones et lots cliquables), plus le back-office de l'agent de l'AFI et de l'administrateur.

| | |
|---|---|
| **Exigences** | BF5, BF7, BF9, BNF6, BNF7, BNF8, cas d'utilisation 1 à 16 |
| **Contrat** | Appelle l'API du module `dalila/communication` (`POST /carte/chatbot`) et les vues publiques pour la carte. |
| **État** | À faire ; technologie au choix de l'équipe (micro du navigateur : HTTPS obligatoire). |
