# Décisions

Les choix en vigueur et leurs preuves (2026-11-26). Les décisions sur chaque donnée (prix, distance, lot…) sont dans
[db/corrections/DESACCORDS.md](../db/corrections/DESACCORDS.md).

## Architecture

| Décision | Preuve |
|---|---|
| **Base propre à Dalila (option b)** : MariaDB 11.8 avec une **copie** des tables de l'AFI (afi.sql), rafraîchie depuis la carte publique de l'AFI par `dalila.connaissances.rafraichir_copie_afi` ; Dalila ne touche pas à la base de l'AFI. | Rafraîchissement limité : la carte est protégée contre les robots (CAPTCHA le 2026-11-27 après ~200 requêtes). Le script s'arrête sans rien écrire ; pour un rafraîchissement régulier, accès ou export à demander à l'AFI. La base de connaissances de l'AFI n'est pas sur la carte : elle reste celle d'afi.sql. |
| **MariaDB 11.8 LTS, source unique.** `afi.sql` chargé tel quel ; nos tables à côté. | Les vues donnent 673 lots disponibles, comme la carte publique de l'AFI (672) plus un lot à confirmer. `dalila_ro` ne peut pas lire `lots` (donc ni `LOT_PROMOTEUR`) ni les tables AFI. |
| **Les données de l'AFI sont lues en direct, jamais copiées.** Les vues `v_pub_*` lisent zones, lots, distances, équipements et services ; les réponses validées de l'AFI sont relues à chaque chargement. | Un changement dans la base AFI (étape d'un lot, prix) se voit tout de suite dans les vues ; testé. |
| **Corrections avec garde-fou.** Chaque correction garde la valeur AFI d'origine ; si l'AFI la change, la correction devient « périmée » et la valeur de l'AFI s'affiche (`v_dalila_corrections_etat`). | Testé : prix modifié dans la base → correction périmée, nouvelle valeur affichée. |
| **Un chiffre n'est stocké qu'une fois** : comptes calculés par les vues ; ni prix, ni distance, ni compte dans le graphe ni dans les passages (fiches de zone sans chiffre). | Règle SHACL `PasDeChiffresMetier` : 0 violation. |
| **Seuls les lots cessibles** (`LOT_NATURE` = 1) sont proposés, comme sur la carte de l'AFI. | Les 7 autres lots « disponibles » de la base sont des équipements publics, absents de la carte. |
| **Passages et vecteurs dans MariaDB** (colonne `VECTOR`, `VEC_DISTANCE_COSINE`, recherche exacte). | 8 858 passages. |
| **Ontologie écrite à la main**, faits générés depuis la base ; **SHACL** et **OWL RL** à chaque construction ; **Oxigraph** embarqué, graphes nommés `core`, `abox`, `lexique`, `a-valider`, `appris/<id>`. | SHACL conforme ; OWL RL : 0 erreur ; 11 requêtes de test répondent. |
| **Anciens noms des zones** (« ENFIDHA 2 », « KASSERINE 2 »…) : `skos:hiddenLabel`, reconnus dans les questions, jamais affichés. | « Enfidha 2 » → zone ENNFIDHA II ; « Gaafour » → GAFOUR. |
| **8 langues** ; traductions non vérifiées isolées dans le graphe `a-valider`. | fr, en, ar, de, tr, aeb, arq, ayl ; de/tr/arq/ayl à valider. |
| **Recherche guidée par le graphe** : zone reconnue → seulement son cahier des charges ; régime de la zone → fiches AFI du bon régime ; démarche → réponses validées de l'AFI en tête ; langue de la question en premier. | |

## Données

| Décision | Preuve |
|---|---|
| **Les données actuelles de l'AFI l'emportent** sur l'ancienne carte publique (afi.e-industrie.gov.tn) relevée pour la fusion. | La carte actuelle (carte.afi.nat.tn) donne les valeurs de la base pour 250/250 champs de zones, 528/528 distances et équipements, 2 955/2 958 lots ; les 3 lots restants ont été changés par l'AFI depuis l'export et sont corrigés. Nos contrôles (GPS des zones, contours des lots, site de l'AFI) donnent tort à l'ancienne carte chaque fois qu'ils permettent de trancher. |
| **Corpus nettoyé une fois** (`preparer_corpus`) : copies de tables AFI retirées, 227 doublons retirés, OCR illisible « secondaire ». | 76 passages OCR marqués (lisibilité < 60 %), dont tout le cahier de la parcelle 15 de Ben Arous (2007). La note n'est pas appliquée à l'arabe (non fiable). |
| **Erreur prouvée dans la base de connaissances de l'AFI** corrigée par extrait (numéro de téléphone de la réponse 3). | Page contact du site AFI et réponse 26. |
| **Groupe 1 ou 2 de chaque zone de développement régional** ajouté (la base AFI dit seulement oui / non), visible seulement tant que l'AFI garde la zone en développement régional. | Carte de la FIPA (décret 2017-389), lue sur le PDF (couleurs) : 3 zones en groupe 1, 27 en groupe 2. |
| **Plans de lotissement** : liens publics lus en direct dans la table AFI `zone_documents` (`v_pub_plans`). | Les 45 plans de la table répondent sur carte.afi.nat.tn/storage (vérifié le 2026-11-27). |

## Orientations de l'équipe (à mettre en œuvre)

| Décision | Ce que le code fait aujourd'hui | À faire |
|---|---|---|
| **RAG agentique avec des modèles locaux uniquement** (Ollama ; aucun service d'IA externe, aucune clé) : le modèle choisit lui-même ses sources (passages par le sens, graphe, chiffres des vues) par appels d'outils. Le serveur de l'AFI n'a pas de carte graphique (8 vCPU, 16 Go) : modèle assez petit pour répondre en 35 s au plus (BNF2). | `dalila/harnais/pipeline_fixe.py` enchaîne toujours les mêmes étapes (graphe → chiffres → passages). | Exposer `chercher_passages`, `interroger_graphe` et les fonctions de `outils.py` comme outils de l'agent ; `dalila.py` disparaît. |
| **Pile propre à l'équipe, sans Laravel** : aucun code de l'application existante n'est fourni et l'équipe ne connaît pas Laravel. Service Python avec une API HTTP, interface libre. Le contrat `POST /carte/chatbot` (message, history, lang, contexte → message avec `[[ZONE]]`, `[[LOT]]`, `[[CHOIX]]`, `[[PDF]]`, log_id, source, action) est gardé pour que l'AFI puisse brancher le service plus tard (BNF11). | Pas d'API ni d'interface. | API HTTP (FastAPI) au contrat de `/carte/chatbot` ; interface choisie par l'équipe. |
| **Dalila = un harnais d'agent** : boucle d'outils typés et bornés, garde-fous en entrée et en sortie, couches de sécurité, repli sans erreur brute. | — | Voir « Le harnais de l'agent » ci-dessous. |
| **Pas de règles écrites à la main pour les langues** (pas d'expressions régulières ni de listes par langue). | `recherche.langue_de` (compte des lettres arabes), listes de mots vides (`comprendre.py`, `recherche.py`), normaliseur du lexique (`dalila/langue/lexique/`). | Laisser le modèle détecter la langue et reformuler la question ; un modèle de recherche multilingue (ajusté si besoin) remplace le lexique. |

## Ajustement des modèles (à faire, après mesure)

Le modèle de recherche (BGE-M3) sera ajusté sur nos propres paires, puis remesuré sur le jeu de vraies questions,
**jamais utilisé pour l'entraînement**. Paires disponibles sans rien inventer :

| Tâche | Paires (entrée → cible) | Pourquoi |
|---|---|---|
| Relier un projet à la nomenclature (`conseiller`) | description d'un projet, dans les 8 langues et en arabizi → activité de la nomenclature de l'APII (501 libellés) | Aujourd'hui, la bonne activité est dans les 5 premières (12 cas sur 12) mais pas toujours première ; les libellés courts se distinguent mal. |
| Trouver la réponse de l'AFI (`chercher_passages`, `demarche`) | question de visiteur → réponse validée de l'AFI (85) ou passage qui y répond | Rappel@5 de 12/15 sur les vraies questions ; le tunisien reste le point faible (22/30). |

Les paraphrases dans les 8 langues sont produites par le modèle local à partir des libellés et des réponses de l'AFI,
puis vérifiées automatiquement (retrouvent-elles leur cible ?) ; les corpus tunisiens (TArC, TUNIZI, TSAC) apportent
l'écriture réelle (licences : démonstration seulement pour TArC).

## Le harnais de l'agent (à construire)

Le cahier des charges n'emploie pas le mot « harnais », mais il exige presque toutes ses couches. Chaque couche est
testée par un jeu de questions dédié (dont des attaques), à chaque changement.

| Couche | Ce qu'elle fait | Exigé par |
|---|---|---|
| **Entrée** | Message de 500 caractères au plus, historique de 20 messages au plus ; données personnelles (téléphone, CIN, RNE, noms) masquées avant le modèle et avant tout journal. | F01, F10, BNF9, BNF16 |
| **Injection d'instructions** | Une question, une page web ou un passage ne peut jamais changer les consignes : les textes lus sont passés au modèle comme des données balisées, jamais comme des instructions ; seules les URL configurées sont lues. | VI.4, BNF14 |
| **Compréhension** | Le modèle local détecte la langue et l'écriture (8 langues, arabizi, mélange avec le français) et ramène la question à une forme comprise ; aucune règle écrite à la main. | BF1, BF2, BF3 |
| **Outils** | Liste fermée d'outils typés (schémas d'entrée et de sortie), lecture seule par le compte `dalila_ro` ; nombre d'étapes et temps bornés (35 s au total). Les questions larges reçoivent une question à choix (`[[CHOIX]]`). | BF4, BF10, BF22, BNF2 |
| **Actions** | Une action réelle (demande d'acquisition) est seulement préparée : brouillon prérempli, jamais déposé sans la confirmation du promoteur. | BF11 |
| **Ancrage de la réponse** | Avant l'envoi, chaque chiffre (prix, surface, nombre, distance, frais) doit se trouver dans les résultats des outils, chaque balise `[[ZONE]]`, `[[LOT]]`, `[[PDF]]` doit viser un identifiant rendu par un outil, chaque texte cité garde sa source ; sinon la réponse est refaite, ou remplacée par une réponse construite directement à partir des faits. | BNF1, BF5, BF23, BNF13 |
| **Règles métier** | Information absente : le dire et donner le contact de l'AFI ; service non couvert : contact AFI et besoin enregistré ; aucun montant de subvention calculé ; hors sujet : refus poli. | BF6, BF24, limites.md |
| **Repli** | Moteur ou voix en panne : réponse en texte depuis la base de connaissances ou les faits, jamais de message d'erreur brut. | BNF4, BNF7 |
| **Apprentissage sûr** | Un ajout exige plusieurs conversations distinctes, une source vérifiable, un graphe cohérent (SHACL, OWL) et aucune baisse sur le jeu de test ; jamais un prix, une disponibilité ou une condition venus d'un visiteur ; journal, annulation, versions. | BF18, BF19, BF21, BNF15, BNF17, BNF18 |
| **Journal et mesures** | Chaque tour (anonymisé) garde la langue, les outils appelés, les verdicts des garde-fous et le temps ; base du tableau de mesures des livrables. | Livrables, BF12 |

## Modèle de recherche

**Choix : BGE-M3 (BAAI/bge-m3), sans reranker.** Mesuré le 2026-11-27 sur les 8 858 passages, mêmes questions, même
graphe (`python -m eval.comparer_modeles`, `python -m eval.vitesse_cpu`) :

| Réglage | Vraies questions (15) | Tunisien (30) | 8 langues (16) | Question encodée sur processeur (8 fils) |
|---|---|---|---|---|
| e5-small (ancien défaut) | 11/15, MRR 0,48 | 20/30, MRR 0,52 | 14/16, MRR 0,80 | 10 ms |
| **BGE-M3** | **12/15, MRR 0,70** | 22/30, MRR 0,60 | **16/16, MRR 0,93** | 77 ms |
| Qwen3-Embedding-0.6B | 11/15, MRR 0,61 | **22/30, MRR 0,65** | 16/16, MRR 0,87 | 532 ms |
| + reranker bge-reranker-v2-m3 | moins bon avec chaque modèle | | | 15 s pour 20 passages |

- Rappel@5 : la bonne réponse est dans les 5 premiers passages ; MRR : 1 si elle est première.
- BGE-M3 gagne sur le jeu principal (vraies questions de visiteurs) et sur les 8 langues, et reste rapide sur le
  processeur du serveur de l'AFI. Qwen3 fait un peu mieux sur le tunisien : à reprendre avec l'ajustement du modèle.
- Le reranker baisse les résultats et coûterait 15 s par question sans carte graphique : désactivé.
- Recherche exacte dans MariaDB : environ 1,7 s par question pour BGE-M3 (0,3 s pour Qwen3, même taille de vecteur :
  effet de stockage). Un index de vecteurs le ramènera à quelques millisecondes ; même sans, la réponse reste loin du
  budget de 35 s.

## Reporté

- SICAD et APIA : seulement les extraits de la base AFI (le module sources lira les URL configurées) ; INS et ministères : cités seulement, comme le prévoit le cahier des charges (voir limites.md).
- Jeu de test de l'équipe à écrire (`eval/testset/MODELE_questions.csv`) : les 24 questions d'exemple, écrites par Claude, sont faciles et ne comptent pas dans le score officiel.
