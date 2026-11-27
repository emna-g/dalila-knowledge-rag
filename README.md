# Dalila : l'agent IA de l'AFI

**Dalila**, l'assistant IA de l'AFI (Agence Foncière Industrielle), Hackathon AGENTIC 2026, répond par une API HTTP
textuelle à partir des **données de l'AFI** (zones, lots, prix) et des **sources officielles** (cahiers des charges,
AFI, TIA, FIPA, APII, SICAD, APIA…). L'agent appelle des outils bornés et vérifie l'ancrage des réponses. Le parcours
vocal et le frontend ne sont pas encore implémentés. Les modèles tournent localement.

## Structure du dépôt

Le paquet `dalila/` suit les modules du cahier des charges (section VI.3). Chaque module a un `README.md` : rôle,
exigences couvertes, contrat, état. La carte complète des exigences et de leur état est dans
[docs/exigences.md](docs/exigences.md).

```
dalila/                 le service (paquet Python)
├─ communication/       API FastAPI chat et carte                           implémentée, intégration réelle à valider
├─ harnais/             agent, garde-fous, outils bornés, réponse de repli   implémenté, intégration réelle à valider
├─ traitement/          outils métier et carte                              implémentés, Gafsa reste incomplet
├─ semantique/          graphe (compréhension) et recherche par le sens     existant
├─ langue/              normalisation et lexique tunisien                   partiel
├─ voix/                voix vers texte, texte vers voix                    non implémenté
├─ sources/             préparation du corpus, ingestion périodique         partiel
├─ apprentissage/       boucle d'apprentissage contrôlée                    à faire
├─ administration/      supervision, connaissances, réglages, droits        à faire
├─ moteurs/             Ollama et embeddings locaux; reranker optionnel     implémentés, intégration à valider
├─ connaissances/       construction de la base (MariaDB, vecteurs, graphe) existant
└─ config.py            réglages (.env)
db/                     migrations SQL, corrections relues, références
ontology/               ontologie OWL, règles SHACL, requêtes de test
frontend/               carte interactive et fenêtre de Dalila              non implémenté
eval/                   jeux de questions, évaluation, comparaison des modèles
tests/                  tests unitaires et intégration dépendante des données
deploy/                 Docker Compose (MariaDB, Oxigraph, chargement); API lancée sur l'hôte
scripts/                page de test (tester.bat)
docs/                   architecture, décisions, limites, exigences
donnees/  modeles/      hors git : afi.sql et corpus, modèles téléchargés
```

| Brique | Où | Rôle |
|---|---|---|
| **MariaDB 11.8** | `db/` | Copie des tables de l'AFI (`afi.sql`, rafraîchie depuis la carte publique). Les vues `v_pub_*` lisent **en direct** zones, lots, prix, distances, équipements, services et plans ; les corrections relues (`db/corrections/`) s'y appliquent tant que l'AFI n'a pas changé la valeur. Nos tables `dalila_*` gardent seulement ce que l'AFI n'a pas : textes à citer et leurs vecteurs, gouvernorats, cahiers, groupes, corrections. Les 24 codes de gouvernorat sont présents; le code 8/Gafsa est sourcé à partir de la ligne AFI `zones.code_zone=932001`. |
| **Graphe (Oxigraph)** | `ontology/` | Le **sens** : ontologie écrite à la main, faits générés depuis la base (aucun chiffre), règles SHACL, graphes nommés. |
| **Évaluation** | `eval/` | Rappel@5, MRR, chiffres exacts, temps de réponse, sur de vraies questions de visiteurs. |

À lire aussi : **[docs/architecture.md](docs/architecture.md)** (la mécanique, fichier par fichier), **[docs/decisions.md](docs/decisions.md)** (les choix
et leurs preuves), **[docs/limites.md](docs/limites.md)** (ce qui manque), **[docs/exigences.md](docs/exigences.md)** (chaque exigence du cahier des charges, son module et son état), **[db/corrections/DESACCORDS.md](db/corrections/DESACCORDS.md)**
(chaque décision sur les données, avec les deux valeurs).

## Installer (Windows, sans Docker)

1. **MariaDB 11.8** (type `VECTOR`). Charger `afi.sql` **tel quel** dans une base `afi` (utf8mb4).
2. Copier `.env.example` en `.env` et le remplir (connexion et mots de passe des comptes `dalila_ro`, `dalila_rw` et `dalila_ingest`; le compte ingest est créé par la migration 004).
3. **Python 3.10 à 3.12** :
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
   Avec une carte graphique NVIDIA récente (pilote CUDA 13), l'index `cu130` ci-dessus ; sans carte graphique, remplacer
   `cu130` par `cpu` (les vecteurs des grands modèles prennent alors plusieurs heures).
4. **Corpus** (hors git, Drive de l'équipe) : `donnees/corpus/passages.jsonl` et `donnees/corpus/pages_web.jsonl`.
   Ils sont produits une fois par `dalila.connaissances.preparer_corpus` à partir de l'archive de la fusion (voir docs/architecture.md).

## Construire (dans l'ordre)

### Base existante

Appliquer uniquement la migration ciblée après sauvegarde et vérification des
prérequis décrits dans [db/migrations/README.md](db/migrations/README.md), puis
charger les données. Le chargement standard ne lance aucune migration et ne
supprime aucune ligne :

```
.venv\Scripts\python -m dalila.connaissances.migrer --migration 004_reference_contract.sql
.venv\Scripts\python -m dalila.connaissances.charger          upserts DALILA avec le compte dédié, sans migration ni effacement
.venv\Scripts\python -m dalila.connaissances.construire_abox  graphe : génération, SHACL, OWL RL, Oxigraph, requêtes de test
```

### Valider la recherche avant l'index complet

Le modèle par défaut est E5, plus léger. Faites d'abord ce contrôle sur une base
de développement/test préparée; il ne lance ni BGE-M3 ni l'index complet :

```
.venv\Scripts\python -m dalila.connaissances.echantillon --taille 1500
.venv\Scripts\python -m dalila.connaissances.vectoriser --modele e5 --echantillon
.venv\Scripts\python -m eval.run_eval --modele e5 --echantillon
```

`echantillon` reconstruit la table de sélection d'évaluation. La commande écrit
dans la base et remplace les anciennes lignes de cette table; ne l'exécutez pas
sur la base AFI actuelle sans autorisation et sauvegarde. `eval.run_eval`
mesure la recherche historique, pas la qualité de réponse de l'agent.

Après examen des résultats et autorisation explicite, l'index complet exige
l'option `--index-complet` :

```
.venv\Scripts\python -m dalila.connaissances.vectoriser --modele e5 --index-complet
```

Choisir `--modele bge` ou `qwen3` uniquement après cette validation; ces modèles
peuvent prendre plusieurs heures sur CPU.

### Lancer l'API chat

L'API utilise MariaDB publiée sur `127.0.0.1` et Ollama sur l'hôte. Compose ne
contient pas de service API; lancez-la depuis le venv Windows après avoir
configuré `DALILA_MODELE=e5` dans `.env` et vérifié la disponibilité d'Ollama :

```
py -3.12 -m uvicorn dalila.communication.api:app --host 127.0.0.1 --port 8000
```

La page OpenAPI est sur `http://127.0.0.1:8000/docs`. `scripts/tester.bat` et
`eval.run_eval` utilisent encore `pipeline_fixe` : ils ne démontrent pas le
nouvel agent HTTP.

### Base neuve uniquement — parcours destructif

Les migrations historiques contiennent des suppressions de tables. Ne lancer
ces commandes que pour initialiser une base neuve. La procédure exige deux
options de confirmation distinctes et refuse les objets ou comptes DALILA
déjà présents :

```
.venv\Scripts\python -m dalila.connaissances.migrer --all --allow-destructive-history
.venv\Scripts\python -m dalila.connaissances.charger --replace-dalila-data --confirm-replace-dalila-data --surfaces
```

Le chargeur standard est un upsert avec le compte dédié `dalila_ingest`; il ne
retire pas les références absentes des fichiers source et ne recalcule pas les
surfaces KML par défaut. Le remplacement explicite requiert root, vide les
tables DALILA listées dans le chargeur avant de les recharger et ne doit pas
être utilisé sur une base contenant des données à conserver.

Pour remettre la copie des tables de l'AFI à jour (au plus une fois par semaine : la carte de l'AFI bloque les robots) :
```
.venv\Scripts\python -m dalila.connaissances.rafraichir_copie_afi              montre les différences
.venv\Scripts\python -m dalila.connaissances.rafraichir_copie_afi --appliquer  les écrit, puis relancer charger et construire_abox
```

Pour revoir les décisions sur les données (rarement) :
```
.venv\Scripts\python -m dalila.connaissances.lire_carte_afi        relevé de la carte publique actuelle de l'AFI
.venv\Scripts\python -m dalila.connaissances.extraire_corrections  réécrit db/corrections/ et DESACCORDS.md
```

## Tester

- `scripts/tester.bat` (double-clic) : outil historique sans LLM, basé sur `pipeline_fixe`.
- `.venv\Scripts\python -m eval.run_eval --modele e5 --echantillon` : mesure la recherche, pas les réponses du nouvel agent.
- `.venv\Scripts\python -m dalila.langue.lexique.tests.tester_lexique` : tests du lexique tunisien.
- `tests/traitement/test_outils.py` est une intégration réelle, ignorée par défaut. Pour l'exécuter, préparer une base
  isolée préfixée `dalila_test_` avec les migrations ciblées, les références, le corpus et l'ontologie, puis définir
  `DALILA_TEST_DB_NAME` sur son nom avant `py -3.12 -m pytest tests/traitement/test_outils.py`. Le test refuse tout
  schéma ne portant pas ce préfixe et ne se connecte jamais implicitement à la base `DB_NAME` de `.env`.

## Avec Docker

Depuis `deploy/`, avec le `.env` de la racine ; `afi.sql` dans `donnees/afi.sql`, le corpus dans `donnees/corpus/` :

MariaDB est publiée uniquement sur `127.0.0.1:${DB_PORT:-3306}` pour les processus exécutés sur Windows ; les services Compose utilisent le réseau interne (`db:3306`). Elle n'est pas exposée au réseau local.

```
docker compose --env-file ../.env up -d db                         MariaDB 11.8 ; afi.sql chargé tel quel au 1er démarrage
docker compose --env-file ../.env --profile build run --rm ingest  chargement et graphe, sans migration ni vectorisation
docker compose --env-file ../.env --profile e5-sample run --rm e5-sample  échantillon + vecteurs E5 (écrit dans MariaDB)
$env:DALILA_CONFIRM_FRESH_DATABASE='I_ACCEPT_DESTRUCTIVE_FRESH_DATABASE'
docker compose --env-file ../.env --profile fresh-database run --rm bootstrap  initialisation destructive, base neuve uniquement
Remove-Item Env:DALILA_CONFIRM_FRESH_DATABASE
# Index complet seulement après l'évaluation E5 :
$env:DALILA_CONFIRM_FULL_VECTORIZATION='I_ACCEPT_FULL_VECTORIZATION'
docker compose --env-file ../.env --profile full-vectorization run --rm full-vectorization
Remove-Item Env:DALILA_CONFIRM_FULL_VECTORIZATION
docker compose --env-file ../.env run --rm kg load --location /data --file /graphe/dalila.trig
docker compose --env-file ../.env up -d kg                         graphe dans Oxigraph, SPARQL : http://localhost:7878
docker compose --env-file ../.env --profile eval run --rm eval     évaluation, rapports dans eval/reports/
```

L'API et Ollama restent des processus sur l'hôte pour ce parcours local; ils ne
sont pas démarrés par Compose. L'image Oxigraph utilise encore le tag mutable
`latest`; épingler une version avant un déploiement reproductible.

## Règles

- Un chiffre (prix, surface, disponibilité, distance) vient **toujours** des vues `v_pub_*`, jamais d'un passage ni du graphe.
- Le compte `dalila_ro` n'a aucun accès à la table AFI `lots` : les noms des acquéreurs (`LOT_PROMOTEUR`) et les contrats lui sont inaccessibles.
- Les chargements et vecteurs utilisent `dalila_ingest`, limité aux tables et vues nécessaires; root reste réservé aux migrations, à la maintenance de la copie AFI et au remplacement explicitement destructif.
- Les données de l'AFI ne sont jamais copiées : une correction garde la valeur AFI d'origine et cesse de s'appliquer si l'AFI la change.
- Les libellés non vérifiés (allemand, turc, algérien, libyen, formes tunisiennes non attestées) sont dans le graphe nommé **a-valider**.
- Lexique : `translitteration_arabizi_tarc.csv` et `variantes_arabizi_tarc.csv` dérivent du corpus TArC (CC BY-NC-SA 4.0) : **démo seulement**.
- `afi.sql` et le corpus ne sont jamais dans git ni dans l'image Docker : ils sont montés en lecture seule.
