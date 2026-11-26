# Guide complet : la mécanique de Dalila (version MariaDB + Oxigraph)

## 1. Les concepts, en une ligne

| Mot | Sens simple |
|---|---|
| **MariaDB** | La base de données de l'AFI. On y charge `afi.sql` tel quel, et on y ajoute nos tables. Tous les **chiffres** et tous les **textes** y sont. |
| **Vue `v_pub_*`** | Une « fenêtre » sur la base qui ne montre que ce qui est public : jamais les noms des acquéreurs. Les comptes (lots disponibles…) y sont **calculés**, pas stockés. |
| **Vecteur (embedding)** | Une liste de nombres qui résume le sens d'un passage. MariaDB 11.8 les range dans une colonne `VECTOR` et calcule la distance (`VEC_DISTANCE_COSINE`). |
| **Ontologie** | La liste des types de choses (zone, lot, service, pièce à fournir…) et de leurs liens. Écrite à la main dans `ontology/dalila.ttl`. |
| **ABox** | Les faits réels rangés selon l'ontologie (« Sidi Achour est dans La Manouba »). Générés depuis la base. |
| **Graphe nommé** | Un « tiroir » du graphe : `core` (ontologie), `abox` (faits), `lexique` (formes attestées), `a-valider` (traductions à relire), `appris/<id>` (futur apprentissage ; annuler = vider le tiroir). |
| **SHACL** | Des règles que le graphe doit respecter (une zone a un seul gouvernorat, pas de prix dans le graphe…). Vérifiées à chaque construction. |
| **Oxigraph** | Le moteur qui garde le graphe et répond aux requêtes SPARQL, embarqué dans Python (`pyoxigraph`). |
| **RRF** | Façon de fusionner deux classements (par le sens, par les mots-clés) : un passage bien placé dans les deux passe devant. |
| **Reranker** | Un second modèle qui relit la question et chaque passage ensemble pour réordonner les meilleurs. Plus précis, mais plus lent. |

**Règle d'or :** un chiffre vient toujours des vues MariaDB. Le graphe donne le sens. Les passages donnent les textes à citer.

## 2. Le trajet d'une question

Exemple : « quels sont les comodités prés de la zone industrielle sidi achour borj el amri ».

1. **Graphe** (`comprendre.py`) : reconnaît la zone **Sidi Achour Borj El Amri** (nom long, 5 mots) et l'idée **Commodité** malgré la faute (« comodités »). Intention : *commodités d'une zone*.
2. **Chiffres** (`outils.py`, vues MariaDB) : fiche de la zone — prix au m², lots disponibles (calculés), infrastructures et distances, équipements, **11 services proches** (lycée à 2,4 km, poste à 7,1 km…), cahier des charges.
3. **Passages** (`recherche.py`) : filtre SQL (seulement le cahier des charges de **cette** zone, pas des autres), recherche par le sens dans MariaDB + mots-clés, fusion, langue de la question en premier.
4. **LLM** (pas encore branché) : rédigerait avec ces seuls éléments, en citant les sources.

## 3. Les fichiers

| Fichier | Ce qu'il fait |
|---|---|
| `db/migrations/001_dalila_tables.sql` | Crée nos tables à côté de celles de l'AFI : zones vérifiées, distances, équipements, services proches, statut des lots, cahiers, registre des sources, **passages + vecteurs**, et tables `agent_*` (journal, apprentissage). |
| `db/migrations/002_views.sql` | Les vues publiques `v_pub_*`, avec les comptes calculés. |
| `db/migrations/003_users.sql` | Deux comptes : `dalila_ro` (lit seulement les vues) et `dalila_rw` (écrit les tables `agent_*`). |
| `backend/config.py` | Réglages : connexion à la base (fichier `.env`), dossiers, modèle de recherche. |
| `backend/ingest/migrer.py` | Applique les 3 fichiers SQL. |
| `backend/ingest/charger_fusion.py` | Remplit nos tables depuis `dalila_fusion` ; écarte les doublons exacts de passages. |
| `backend/ingest/vectoriser.py` | Calcule les vecteurs (e5 ou BGE-M3) et les range dans MariaDB. |
| `backend/ingest/echantillon.py` | Échantillon commun de 1 500 passages pour comparer les modèles. |
| `backend/ingest/construire_abox.py` | Génère les faits du graphe, applique SHACL et OWL RL, charge Oxigraph, lance les requêtes de test. |
| `ontology/dalila.ttl` | L'ontologie, écrite à la main (10 familles et sous-classes, relations). |
| `ontology/shapes.ttl` | Les règles SHACL. |
| `ontology/libelles_a_valider.ttl` | Les noms des 9 familles en 8 langues, **écrits par Claude, à relire**. |
| `ontology/queries/*.rq` | Une requête de test par famille, plus BF17 (synonymes) et BF20 (raisonnement). |
| `ontology/abox/rapport_graphe.json` | Résultat de la dernière construction (nombres de faits, SHACL, OWL RL, requêtes). |
| `backend/app/comprendre.py` | Relie la question aux concepts du graphe (zones, gouvernorats, commodités, services). |
| `backend/app/outils.py` | Les chiffres : lots disponibles, fiche de zone, zones proches d'un port… (vues MariaDB). |
| `backend/app/recherche.py` | La recherche des passages dans MariaDB. |
| `backend/app/dalila.py` | Assemble les trois. |
| `tester.py` / `tester.bat` | Pose une question, une page s'ouvre dans le navigateur. |
| `eval/run_eval.py` | L'évaluation ; résultats dans `eval/reports/`. |
| `eval/testset/` | Modèle de jeu de test et 24 questions d'exemple écrites par Claude (à relire). |
| `lexicon/` | Le lexique tunisien et son normaliseur. |
| `ancien_sqlite_chroma/` | L'ancienne version, gardée pour comparaison. |

## 4. Ce que contient le graphe

- **Lieux** : 23 gouvernorats, les 50 zones visibles dans la base (avec leur régime : développement régional ou littoral / Grand Tunis).
- **Lots** : le lien lot → zone seulement.
- **Commodités** : 5 types d'infrastructures, 5 types d'équipements, 11 types de services proches, et quelles zones en ont (les valeurs sont dans la base).
- **Secteurs** : 17 secteurs et 484 activités de la nomenclature de l'APII, plus « pêche et aquaculture » (exemple BF20 du cahier des charges).
- **Démarches** : 8 services de l'AFI, leurs procédures, 44 étapes, 78 pièces à fournir et 5 frais, tirés des fiches 12 à 25 de la base AFI.
- **Incitations** : les 11 avantages des zones 1 et 2 du développement régional, cités mot pour mot depuis la TIA.
- **Organismes** : AFI, APII, TIA, FIPA, APIA, SICAD, ANPE, GMG.
- **Libellés** : français partout ; formes tunisiennes attestées (lexique) ; traductions des familles en 8 langues **à valider**.
