# Exigences du cahier des charges : où et où en est-on

Chaque besoin du cahier des charges (BF : fonctionnel, BNF : non fonctionnel), le module qui le porte et son état.
**À tenir à jour** à chaque étape : c'est la carte de ce qui reste à faire. État au 2026-11-27.
Légende : **Fait** (vérifié), **Partiel** (une partie existe ou n'est pas mesurée), **À faire**.

## Besoins fonctionnels

| Réf. | Besoin (résumé) | Priorité | Module | État |
|---|---|---|---|---|
| BF1 | Détecter la langue parmi les 8, distinguer tunisien, algérien, libyen, arabe standard | Obligatoire | `dalila/langue` | À faire (le lexique détecte le tunisien : 31/32 sur son jeu ; règle écrite à la main, à remplacer) |
| BF2 | Comprendre le tunisien, mêlé de français, sans orthographe fixe | Obligatoire | `dalila/langue`, `dalila/semantique` | Partiel (lexique attesté ; recherche 20/30 sur le jeu tunisien) |
| BF3 | Répondre dans la langue et l'écriture du visiteur | Obligatoire | `dalila/langue` | À faire |
| BF4 | Fonctions existantes dans les 8 langues (terrain, proximité, qualification, procédure, étude) | Obligatoire | `dalila/traitement`, `dalila/harnais` | Partiel (outils terrain, proximité, procédures faits et testés ; qualification et étude : à faire ; 8 langues : avec le harnais) |
| BF5 | Garder zones cliquables et boutons de choix après reformulation | Obligatoire | `dalila/communication`, `dalila/harnais` | À faire |
| BF6 | Dire quand l'information manque, orienter vers l'AFI | Obligatoire | `dalila/harnais` | Partiel (les manques sont connus : docs/limites.md) |
| BF7 | Poser une question à la voix dans les 8 langues | Obligatoire | `dalila/voix`, `frontend` | À faire |
| BF8 | Lire la réponse à voix haute | Obligatoire | `dalila/voix` | À faire |
| BF9 | Activer ou couper micro et lecture | Obligatoire | `frontend` | À faire |
| BF10 | Enchaîner plusieurs actions (agent à outils) | Souhaité | `dalila/harnais`, `dalila/traitement` | À faire |
| BF11 | Préparer une demande d'acquisition, sans dépôt sans confirmation | Souhaité | `dalila/traitement`, `dalila/harnais` | À faire |
| BF12 | Lister pour l'AFI les questions en dialecte mal comprises | Souhaité | `dalila/apprentissage`, `dalila/administration` | À faire (table `agent_needs` créée) |
| BF13 | Conversation vocale continue | Souhaité | `dalila/voix`, `frontend` | À faire |
| BF14 | Lire les URL de la configuration, répondre avec le lien de la source | Obligatoire | `dalila/sources` | Partiel (corpus des sites officiels lu une fois ; lecture par configuration à faire) |
| BF15 | État de chaque URL (lecture, échec, relance), PDF compris | Souhaité | `dalila/sources`, `dalila/administration` | À faire (table `agent_source_status` créée) |
| BF16 | Ontologie OWL/RDF, 9 familles, 8 langues | Obligatoire | `ontology/`, `dalila/connaissances` | Fait pour les familles (SHACL conforme, OWL RL sans erreur, une requête par famille) ; libellés de/tr/dz/ly à relire |
| BF17 | Comprendre par le sens, pas seulement par mots-clés | Obligatoire | `dalila/semantique`, `dalila/traitement/graphe.py` | Partiel (recherche par le sens : BGE-M3 choisi, voir decisions.md ; outil `relier_concepts` sur le graphe ; correspondance des activités par le sens à faire) |
| BF18 | Apprendre des questions mal comprises, fréquentes, mal notées | Obligatoire | `dalila/apprentissage` | À faire |
| BF19 | Contrôler automatiquement puis publier ce qui est appris | Obligatoire | `dalila/apprentissage` | À faire (contrôles SHACL / OWL / requêtes déjà en place dans construire_abox) |
| BF20 | Raisonner sur le graphe pour conseiller | Souhaité | `dalila/semantique` | Partiel (requête de test BF20 : pêche → APIA, port) |
| BF21 | Journal de l'apprentissage et annulation a posteriori | Obligatoire | `dalila/apprentissage`, `dalila/administration` | À faire (graphes nommés `appris/<id>` prévus) |
| BF22 | Guider vers le bon service par des questions à choix | Obligatoire | `dalila/harnais`, `dalila/traitement` | À faire |
| BF23 | Conditions, pièces, frais, lieu de dépôt, lien de chacun des 8 services | Obligatoire | `dalila/traitement`, base de connaissances | Partiel : les 8 services ont conditions ou étapes, pièces et lien (réponses AFI 12 à 25, vérifiées le 2026-11-27, `db/reference/services_afi.csv`) ; manques publiés par l'AFI elle-même : voir docs/limites.md ; l'outil reste à faire |
| BF24 | Service non couvert : contact AFI, besoin enregistré | Obligatoire | `dalila/harnais` | À faire |

## Besoins non fonctionnels

| Réf. | Besoin (résumé) | Cible | Module | État |
|---|---|---|---|---|
| BNF1 | Tout chiffre vient des données de l'AFI | 100 % | `dalila/harnais` (ancrage), vues `v_pub_*` | Partiel (données vérifiées ; ancrage de la réponse à faire) |
| BNF2 | Temps de réponse à l'écrit | ≤ 35 s | `dalila/harnais`, `dalila/moteurs` | À mesurer (sur processeur, sans carte graphique) |
| BNF3 | Reconnaissance vocale | ≤ 4 s | `dalila/voix` | À faire |
| BNF4 | Panne d'une API : réponse en texte quand même | aucune erreur brute | `dalila/harnais` | À faire |
| BNF5 | Français, anglais, arabe sans régression | jeu de test | `eval/` | Partiel (jeux de test en place) |
| BNF6 | Ordinateur, tablette, téléphone ; droite à gauche | 3 formats | `frontend` | À faire |
| BNF7 | Toute réponse vocale existe en texte | toutes | `dalila/voix`, `frontend` | À faire |
| BNF8 | Consentement micro, audio non conservé | démonstration | `frontend`, `dalila/voix` | À faire |
| BNF9 | Clés hors du code, HTTPS, aucune donnée personnelle vers un service externe | aucune clé | tous | Fait pour l'existant (modèles locaux uniquement, `.env` hors git) |
| BNF10 | Moteurs interchangeables par configuration | sans code | `dalila/moteurs` | Partiel (modèle de recherche par `DALILA_MODELE`) |
| BNF11 | Service à part avec une API HTTP, démarrage documenté | — | `dalila/communication`, README | À faire (démarrage de la base documenté) |
| BNF12 | Licence et coût de chaque modèle déclarés | liste complète | `docs/` | À faire (modèles en place : e5, BGE-M3, Qwen3-Embedding, bge-reranker) |
| BNF13 | Mêmes zones et chiffres dans les 8 langues | 100 % | `dalila/harnais`, `eval/` | À faire |
| BNF14 | Seules les URL configurées ; page = donnée, jamais instruction | page piégée sans effet | `dalila/sources`, `dalila/harnais` | À faire |
| BNF15 | Chaque ajout daté, sourcé, contrôlé ; versions | retour arrière | `dalila/apprentissage` | Partiel (graphe précédent gardé à chaque construction) |
| BNF16 | Questions anonymisées avant apprentissage | aucun nom, téléphone, CIN, RNE | `dalila/harnais`, `dalila/apprentissage` | Partiel (jeu de test anonymisé ; filtre automatique à faire) |
| BNF17 | Gain d'apprentissage mesuré avant / après, par langue | hausse | `eval/` | À faire |
| BNF18 | Jamais apprendre un prix, une disponibilité, une condition d'un visiteur ; plusieurs conversations | aucun ajout sans source | `dalila/apprentissage` | À faire |
| BNF19 | OWL 2, RDF, SPARQL 1.1, libellés avec langue, export Turtle | export sans erreur | `ontology/`, `dalila/connaissances` | Fait (export TriG/Turtle, SHACL, OWL RL, requêtes de test) |

## Livrables

| Livrable | Où | État |
|---|---|---|
| Dépôt avec fichier d'installation, sans clé ni donnée personnelle | README.md | Partiel |
| Démonstration écrit et voix, 8 langues, arabizi | `frontend`, `dalila/` | À faire |
| Tableau de mesures (voix, temps, exactitude des chiffres) | `eval/reports/` | Partiel (recherche et chiffres mesurés) |
| Liste des API et modèles, licence et coût | `docs/` | À faire |
| Note d'une page : limites et travail restant | `docs/limites.md` | Partiel |
