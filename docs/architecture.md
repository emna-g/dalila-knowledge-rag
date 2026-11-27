# Guide : la mécanique de Dalila (données et recherche)

## 1. Les concepts, en une ligne

| Mot | Sens simple |
|---|---|
| **Base AFI** | Les tables de l'AFI (`afi.sql` chargé tel quel dans MariaDB) : zones, lots, distances, équipements, services proches, base de connaissances. Dalila les lit **en direct**, sans les copier. |
| **Vue `v_pub_*`** | Une « fenêtre » sur la base qui ne montre que le public (jamais les acquéreurs). Les comptes y sont **calculés**, et les corrections relues y sont appliquées. |
| **Correction** | Une ligne de `db/corrections/dalila_corrections.csv` : valeur AFI d'origine, valeur corrigée, source, raison. Elle cesse de s'appliquer dès que l'AFI change la valeur (« périmée »). |
| **Passage** | Un morceau de texte à citer (cahier des charges, page officielle, réponse validée de l'AFI…), avec sa source et son vecteur. |
| **Vecteur (embedding)** | Une liste de nombres qui résume le sens d'un passage ; MariaDB 11.8 les range dans une colonne `VECTOR` et calcule la distance. |
| **Ontologie / graphe** | Les types de choses (zone, lot, démarche, pièce à fournir…) et leurs liens, écrits à la main (`ontology/dalila.ttl`), plus les faits générés depuis la base. Aucun chiffre. |
| **SHACL** | Les règles que le graphe doit respecter, vérifiées à chaque construction. |
| **RRF** | La fusion de deux classements (par le sens, par les mots-clés). |
| **Reranker** | Un second modèle qui relit la question et chaque passage ensemble pour réordonner les meilleurs. |

**Règle d'or :** un chiffre vient toujours des vues MariaDB. Le graphe donne le sens. Les passages donnent les textes à citer.

## 2. Le trajet d'une question

Exemple : « quels sont les comodités prés de la zone industrielle sidi achour borj el amri ».

1. **Graphe** (`comprendre.py`) : reconnaît la zone (nom long, anciens noms compris) et l'idée *commodité* malgré la faute.
2. **Chiffres** (`outils.py`, vues) : prix au m², lots disponibles (calculés), distances, équipements, services proches, cahier des charges.
3. **Passages** (`recherche.py`) : seulement le cahier des charges de **cette** zone ; recherche par le sens et par mots-clés ; langue de la question en premier ; passages « secondaires » (OCR illisible…) écartés.
4. **LLM** (branché par le backend de l'équipe) : rédige avec ces seuls éléments, en citant les sources.

## 3. D'où viennent les données

| Donnée | Source | Comment elle arrive dans Dalila |
|---|---|---|
| Zones, lots, prix, distances, équipements, services proches | Base AFI | Lue en direct par les vues `v_pub_*` |
| Corrections, lots à confirmer, anciens noms des zones | `db/corrections/` (preuves : `carte_afi_actuelle.json`, `ancienne_carte.json`) | `charger` → `dalila_corrections`, `dalila_lots_a_confirmer`, `dalila_zone_alias` |
| Réponses validées de l'AFI | Base AFI (`chatbot_connaissances`) | `charger` en fait des passages, corrections de texte appliquées |
| Fiches de zone (sans chiffre) | Vues `v_pub_*` | `charger` les écrit à chaque chargement |
| Cahiers des charges, sites officiels (AFI, FIPA, APII, TIA, SICAD, APIA), guides, lois, rapports | `donnees/corpus/passages.jsonl` | `charger` → `dalila_passages` |
| Gouvernorats, liste des cahiers des charges, groupe 1 / 2 du développement régional | `db/reference/` | `charger` → `dalila_gouvernorats`, `dalila_cahiers`, `dalila_zone_groupe_dr` |
| Plans de lotissement | Base AFI (`zone_documents`), fichiers publiés sur la carte de l'AFI | Lus en direct par la vue `v_pub_plans` |

Le corpus (`donnees/corpus/`) a été produit **une fois** par `dalila.connaissances.preparer_corpus` à partir de l'archive de la
fusion des données (zips `dalila_fusion_partie1` et `partie2` du Drive) : copies de tables AFI retirées, doublons retirés,
OCR illisible marqué « secondaire ».

## 4. Les fichiers

| Fichier | Ce qu'il fait |
|---|---|
| `db/migrations/001_dalila_tables.sql` | Nos tables à côté de celles de l'AFI : gouvernorats, corrections, lots à confirmer, noms alternatifs, décodage des étapes et des commodités, cahiers, registre des sources, **passages + vecteurs**, tables `agent_*`. |
| `db/migrations/002_views.sql` | Les vues publiques `v_pub_*` (lecture en direct, corrections, comptes, seulement les lots cessibles) et `v_dalila_corrections_etat` (appliquée, à vérifier, périmée). |
| `db/migrations/003_users.sql` | `dalila_ro` (lit seulement les vues) et `dalila_rw` (écrit les tables `agent_*`). |
| `db/corrections/` | Les décisions sur les données : CSV relus à la main, preuves, et `DESACCORDS.md`. |
| `db/reference/` | Gouvernorats, liste des cahiers des charges (lien du PDF officiel, remarque), groupe 1 ou 2 des zones de développement régional (carte de la FIPA). |
| `dalila/config.py` | Réglages : connexion (`.env`), dossiers, modèle de recherche. |
| `dalila/connaissances/migrer.py` | Applique les fichiers SQL. |
| `dalila/connaissances/charger.py` | Remplit nos tables (références, corrections, passages, réponses AFI, fiches de zone). |
| `dalila/connaissances/vectoriser.py` | Calcule les vecteurs des passages (BGE-M3 par défaut ; e5, Qwen3), sur la carte graphique si elle est là. |
| `dalila/connaissances/construire_abox.py` | Génère les faits du graphe, applique SHACL et OWL RL, charge Oxigraph, lance les requêtes de test. |
| `dalila/connaissances/rafraichir_copie_afi.py` | Remet à jour la copie des tables de l'AFI depuis sa carte publique (champs publics seulement ; s'arrête si la carte demande un CAPTCHA). |
| `dalila/connaissances/lire_carte_afi.py` | Relève la carte publique actuelle de l'AFI (preuve pour les décisions). |
| `dalila/connaissances/extraire_corrections.py` | Compare base AFI, carte actuelle et ancienne carte ; écrit `db/corrections/`. |
| `dalila/connaissances/preparer_corpus.py` | Prépare le corpus à partir de l'archive de la fusion (une fois). |
| `dalila/connaissances/echantillon.py` | Échantillon de passages pour comparer les modèles vite. |
| `dalila/semantique/comprendre.py` | Relie la question aux concepts du graphe (zones et leurs anciens noms, gouvernorats, commodités, services). |
| `dalila/traitement/outils.py` | Les chiffres : lots disponibles, fiche de zone, zones proches… (vues, compte `dalila_ro`). |
| `dalila/semantique/recherche.py` | La recherche des passages dans MariaDB. |
| `dalila/harnais/pipeline_fixe.py` | Assemble les trois. |
| `ontology/` | Ontologie, règles SHACL, libellés à valider, requêtes de test (le graphe généré n'est pas dans git). |
| `dalila/langue/lexique/` | Le lexique tunisien et son normaliseur. |
| `eval/` | L'évaluation et les jeux de test. |
| `scripts/tester.py` / `scripts/tester.bat` | Pose une question, une page s'ouvre dans le navigateur. |
| `deploy/` | Docker Compose : MariaDB, Oxigraph, image Python. |

## 5. Ce que contient le graphe

- **Lieux** : gouvernorats, les 50 zones visibles de la base (régime : développement régional ou littoral), leurs anciens noms (reconnus, jamais affichés).
- **Lots** : le lien lot → zone seulement.
- **Commodités** : types d'infrastructures, d'équipements et de services proches, et quelles zones en ont (les valeurs sont dans la base).
- **Secteurs** : nomenclature de l'APII (17 secteurs, 484 activités).
- **Démarches** : services de l'AFI, procédures, étapes, pièces à fournir et frais (réponses validées de l'AFI).
- **Incitations** : avantages des zones 1 et 2 du développement régional, cités mot pour mot depuis la TIA.
- **Organismes** : AFI, APII, TIA, FIPA, APIA, SICAD, ANPE, GMG.
- **Libellés** : français partout ; formes tunisiennes attestées ; traductions en 8 langues **à valider**.
