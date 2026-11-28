# Reste à faire : où reprendre

État au 2026-11-28, branche `dalila-donnees-recherche`. Référence : le cahier des charges officiel du hackathon
(BF1 à BF24, BNF1 à BNF19, livrables). L'état de chaque exigence est dans [exigences.md](exigences.md) ; les choix et
leurs mesures dans [decisions.md](decisions.md) ; les limites dans [limites.md](limites.md).

Pour chaque point : ce qui manque, où se trouve le code utile, comment s'y prendre.

## 1. Pas encore fait

| Réf. | Ce qui manque | Où | Comment s'y prendre |
|---|---|---|---|
| **Livrable 3** | Fait : [mesures.md](mesures.md) (2026-11-28). | | |
| **Livrable 5** | Fait : [note_limites.md](note_limites.md) (2026-11-28). | | |
| **BF11** | Fait : demande d'acquisition préremplie, PDF après confirmation (`dalila/traitement/demande.py`, `GET /carte/demande`, `POST /carte/demande/pdf`). | Tests : `python -m tests.communication.test_demande`. | |
| **Docker** | Le premier lancement complet n'est **pas encore validé de bout en bout**. Vérifié dans les conteneurs : chargement de `dalila_base.sql.gz`, migrations, textes à citer (8 858, vecteurs gardés), graphe, voix Piper. Non vérifié : fin du téléchargement des modèles Hugging Face, installation du modèle ajusté dans Ollama (erreur « cannot allocate memory » avec 8 Go donnés à Docker), réponse du service. | `docker-compose.yml`, `deploy/`, [docker.md](docker.md) | Donner 12 Go à Docker, `docker compose up --build -d`, suivre `docker compose logs -f`, poser une question ; corriger ce qui casse. |
| **BF35** (souhaité) | **Mémoire par utilisateur** : comptes promoteurs, conversations gardées, résumé de chaque projet (activité, lieu, surface, budget, emplois, lots vus) construit à partir des appels d'outils, donné à l'agent au début de chaque message. Fait : la connexion (comptes, sessions). | `dalila/communication/comptes.py` (comptes, sessions), `dalila/harnais/agent.py` (`note_contexte` : même place que le contexte de la carte) | Rôle `promoteur` ; tables des conversations et des projets ; rangement de chaque échange dans un projet par proximité de l'activité ; écran « Mes projets ». Tester sur des conversations qui sautent d'un projet à l'autre. |
| **BF13** (souhaité) | **Conversation vocale continue**, sans bouton à chaque tour. | Interface : `frontend/app/src/dalila/Dalila.tsx` (micro, lecture) ; service : `/carte/voix/transcrire`, `/carte/voix/lire`. | Côté interface : après la lecture d'une réponse, rouvrir le micro ; arrêt sur silence (détection d'activité vocale dans le navigateur) ; garder l'affichage du texte reconnu (BF7). |
| **Voix tunisienne** (objectif du cahier) | Une **voix tunisienne** pour lire le tunisien. Aujourd'hui : voix arabe standard, en le signalant (BF8 respecté). | `dalila/voix/synthese.py` | Candidat : TunArTTS (Elyadata, Apache 2.0, ESPnet) ; il demande un texte entièrement vocalisé (tashkeel) : trouver ou entraîner un vocaliseur tunisien, puis mesurer à l'écoute. Autres : silma-tts-derja, tunisian-xtts-v1 (cités par le cahier, non évalués). |

## 2. Fait, mais le test d'acceptation du cahier n'a pas été lancé

Le jury apportera ses propres questions : à vérifier en priorité.

| Réf. | Test du cahier des charges | Comment le lancer |
|---|---|---|
| **BF2** | « 3andi projet sardine » et « عندي مشروع سردين » donnent le même résultat. | Deux appels à `/carte/chatbot` ; comparer les outils appelés et les activités rendues. |
| **BF17** | « terrain », « plot », « أرض », « 9at3a » mènent au même concept ; une question reformulée trouve la même connaissance. | Outil `relier_concepts` (caché à l'agent, encore dans le registre) et `chercher_passages` sur des paraphrases. |
| **BF4** | Chaque fonction (terrain, proximité, qualification, procédure, étude) se déclenche **dans chaque langue**. | Comme `eval/bf22_langues.py` (fait pour la procédure : 7/7) ; à étendre aux autres fonctions. |
| **BNF13** | Même question = mêmes zones et mêmes chiffres dans les 6 langues (cible 100 %). | Même question en 6 langues ; comparer les identifiants `[[ZONE]]`, `[[LOT]]` et les nombres rendus. |
| **BNF14** | Une page piégée (« ignore tes consignes… ») ne change pas le comportement de Dalila. | Ajouter une page piégée au corpus de test, poser une question qui la ramène, vérifier la réponse. |
| **BF14** | Une URL ajoutée à la configuration alimente une réponse, sans modifier le code. | `dalila/sources/config_sources.csv`, puis `scripts/rafraichir_sources.bat` ; poser une question sur la page ajoutée. |
| **BNF5** | Français, anglais, arabe : aucune régression. | Le jeu de test réel est surtout en français (49/57) : ajouter des questions en anglais et en arabe, puis `eval/agent_bench.py`. |
| **BNF17** | Gain de l'apprentissage mesuré avant / après, par langue. | Banc d'essai avant et après une publication (`synonymes_appris`, `lieux_appris`). |

## 3. Interface (`frontend/app`)

| Réf. | Ce qui manque | Note |
|---|---|---|
| **BNF6** | Démontrer ordinateur, tablette, téléphone et l'arabe de droite à gauche. | À vérifier sur les 3 formats. |
| **BNF9** | HTTPS en production (le micro du navigateur l'exige). | Nginx du serveur de l'AFI. |
| **BF9** | Couper ou activer la lecture vocale **à tout moment** (aujourd'hui : bouton par réponse). | Un interrupteur global. |
| **BF12, BF21, BF15** | Fait : http://127.0.0.1:8000/admin/ (3 écrans) ; routes `/admin/api/...` (`dalila/communication/admin.py`) ; accès par un compte administrateur connecté (`/connexion/`, `dalila/communication/comptes.py`). | Tests : `python -m tests.communication.test_admin`, `test_comptes`. |
| — | Afficher la note de lecture d'un dialecte et le commentaire d'avis | Fait (commit 5c52345). |

## 4. Points faibles mesurés (pour la suite)

- **Style algérien ou libyen encore produit par le modèle ajusté** (vu le 2026-11-28, après l'abandon de ces
  dialectes) : une question tunisienne écrite à l'algérienne (« n7eb terrain f Sousse ») reçoit la tournure algérienne
  apprise à l'entraînement (« Kayen 4 lots… Li r5as… l metro ») ; une phrase libyenne, la tournure libyenne (« فيه 4 قطع »).
  Langue détectée et chiffres justes ; seule la tournure change. Avec « fi », 5 questions tunisiennes sur 5 reçoivent
  du tunisien. Correction : un nouvel ajustement (le générateur ne produit plus ces exemples) ; pas de remplacement de
  mots écrit à la main.
- **Projet inventé** : « 3andi projet, nlawej 3la ma9sem fi Nabeul » (aucune activité donnée) a reçu « Construction de
  véhicules automobiles… 3 emplois » ; Dalila devrait demander l'activité. À mettre dans les tests de bout en bout.
- **Tunisien brut dans la recherche de passages** : 17/30 sans les anciennes règles (21/30 avec). Piste : ajuster BGE-M3 sur des paires question tunisienne -> passage.
- **Modèle ajusté de l'agent** : questions sur les textes de l'AFI parfois envoyées vers les lots (peu d'exemples de démarches à l'entraînement : 73 sur 816). Piste : un second ajustement avec plus d'exemples, et les conversations réelles exportées (`python -m dalila.apprentissage.exporter`).
- **Arabizi lu à voix haute** : converti en lettres arabes par le dictionnaire du lexique ; les mots inconnus restent en lettres latines et sont mal prononcés.

## 5. Mise en route sur une autre machine

Avec Docker, une commande : **[docker.md](docker.md)** (le dépôt, `.env`, les trois fichiers de `donnees/` reçus d'un
membre de l'équipe, puis `docker compose up --build -d`). Sans Docker : le README, section « Installer (Windows, sans
Docker) », puis les migrations `db/migrations/004` à `008` sur toute base existante.

Tests : `tests/traitement`, `tests/apprentissage`, `tests/voix`, `tests/langue`, `tests/harnais`, `tests/sources`,
`tests/communication` (chacun : `python -m tests.<dossier>.<fichier>` ; avec Docker :
`docker compose run --rm preparer python -m tests.<dossier>.<fichier>`).
