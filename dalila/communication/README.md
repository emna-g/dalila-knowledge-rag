# Module communication

Reçoit les questions et transmet les réponses, les liens et les boutons.

| | |
|---|---|
| **Exigences** | F01 à F06, BF5, BNF11 |
| **Contrat** | API HTTP (FastAPI) au contrat `POST /carte/chatbot` : entrée `message` (500 caractères au plus), `history` (20 messages au plus), `lang`, `contexte` (page, zone, lot, favoris) ; sortie `message` avec les balises `[[ZONE:id:nom]]`, `[[LOT:id:nom]]`, `[[CHOIX:texte]]`, `[[PDF:url:libellé]]`, plus `log_id`, `source`, `action`. Avis (utile / pas utile). |
| **S'appuie sur** | harnais |
| **État** | À faire |
