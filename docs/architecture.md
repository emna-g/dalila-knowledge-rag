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

1. **API** (`communication/api.py`, `service.py`) : valide le contrat HTTP puis transmet la question à `Agent.repondre`.
2. **Agent** (`harnais/agent.py`) : Ollama choisit dans le registre fermé (`traitement/registre.py`) les outils nécessaires; appels, arguments et durée sont bornés.
3. **Faits** (`traitement/*.py`, vues `v_pub_*`) : résout les lieux et lit les prix, lots, distances et démarches. Le graphe peut contribuer à la compréhension et au conseil.
4. **Passages** (`traitement/passages.py`, `semantique/recherche.py`) : recherche les textes citables par vecteurs et mots-clés; le modèle d'embedding vient de `DALILA_MODELE`.
5. **Garde-fous** (`harnais/garde_fous.py`) : vérifie l'ancrage et les balises; le repli est utilisé si l'agent ne peut pas produire une réponse vérifiée.

Le parcours HTTP est implémenté, mais son intégration réelle complète avec MariaDB, le corpus vectorisé et Ollama reste à valider sur une base de test. `scripts/tester.py` et `eval/run_eval.py` utilisent encore `pipeline_fixe.py`; ils ne testent pas ce parcours agent/API.

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
| `db/migrations/003_users.sql` | `dalila_ro` (lecture publique) et `dalila_rw` (écriture des tables `agent_*`). |
| `db/migrations/004_reference_contract.sql` | Références géographiques/prix, échantillon d'évaluation et vues versionnées `*_v2`; les vues publiques historiques restent inchangées. Crée le compte `dalila_ingest` à privilèges limités. |
| `db/corrections/` | Les décisions sur les données : CSV relus à la main, preuves, et `DESACCORDS.md`. |
| `db/reference/` | Gouvernorats, liste des cahiers des charges (lien du PDF officiel, remarque), groupe 1 ou 2 des zones de développement régional (carte de la FIPA). |
| `dalila/config.py`, `.env.example` | Réglages : connexion, dossiers, modèle E5 léger par défaut; `.env` reste local. |
| `dalila/connaissances/migrer.py` | Applique les fichiers SQL. |
| `dalila/connaissances/charger.py` | Remplit nos tables par upsert avec `dalila_ingest`; la suppression nécessite explicitement root et les deux options de confirmation. |
| `dalila/connaissances/synchroniser_references.py` | Synchronise les CSV canoniques par upsert, sans supprimer les références absentes. |
| `dalila/connaissances/vectoriser.py`, `echantillon.py` | E5 échantillonné puis index complet explicitement autorisé; BGE-M3 et Qwen3 après validation. |
| `dalila/connaissances/construire_abox.py` | Génère les faits du graphe, applique SHACL et OWL RL, charge Oxigraph, lance les requêtes de test. |
| `dalila/connaissances/rafraichir_copie_afi.py` | Remet à jour la copie des tables de l'AFI depuis sa carte publique (champs publics seulement ; s'arrête si la carte demande un CAPTCHA). |
| `dalila/connaissances/lire_carte_afi.py` | Relève la carte publique actuelle de l'AFI (preuve pour les décisions). |
| `dalila/connaissances/extraire_corrections.py` | Compare base AFI, carte actuelle et ancienne carte ; écrit `db/corrections/`. |
| `dalila/connaissances/preparer_corpus.py` | Prépare le corpus à partir de l'archive de la fusion (une fois). |
| `dalila/connaissances/echantillon.py` | Échantillon de passages pour comparer les modèles vite. |
| `dalila/semantique/comprendre.py` | Relie la question aux concepts du graphe (zones et leurs anciens noms, gouvernorats, commodités, services). |
| `dalila/traitement/registre.py`, `lieux.py`, `lots.py`, `zones.py`, `passages.py` | Registre et outils actuels de l'agent, avec modèles d'entrée/sortie. |
| `dalila/traitement/carte.py` | Projections de la carte depuis les vues AFI et contours KML, état de disponibilité inconnu si non prouvé. |
| `dalila/traitement/references.py` | Références CSV partagées par les outils, la carte, le chargeur et l'ABox. |
| `dalila/semantique/recherche.py` | La recherche des passages dans MariaDB. |
| `dalila/harnais/agent.py`, `garde_fous.py`, `consignes.py` | Boucle Ollama/outils, règles et validation d'ancrage. |
| `dalila/communication/api.py`, `schemas.py`, `service.py` | API HTTP v1 et contrats d'échange. Elle se lance sur l'hôte; Compose ne démarre pas le serveur HTTP. |
| `dalila/harnais/pipeline_fixe.py`, `dalila/traitement/outils.py` | Ancien parcours encore utilisé par les scripts de test et l'évaluation de recherche. |
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
