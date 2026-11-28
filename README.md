# Dalila : l'agent IA de l'AFI

**Dalila**, l'agente IA de l'AFI (Agence Foncière Industrielle), Hackathon AGENTIC 2026 : elle comprend et parle le
tunisien et les autres langues des investisseurs, à l'écrit et à la voix, et répond à partir des **données de l'AFI**
(zones, lots, prix) et des **sources officielles** (cahiers des charges, AFI, TIA, FIPA, APII, SICAD, APIA…), sans rien
inventer. Service Python avec une API HTTP, modèles locaux uniquement.

## Structure du dépôt

Le paquet `dalila/` suit les modules du cahier des charges (section VI.3). Chaque module a un `README.md` : rôle,
exigences couvertes, contrat, état. La carte complète des exigences et de leur état est dans
[docs/exigences.md](docs/exigences.md).

```
dalila/                 le service (paquet Python)
├─ communication/       API HTTP : /carte/chatbot, /carte/voix/*, /sante    fait
├─ harnais/             boucle d'agent, garde-fous, repli, faits ajoutés    fait (23/35, ≤ 35 s)
├─ traitement/          outils de l'agent : lieux, lots, zones, démarches   fait (9 outils, testés)
├─ semantique/          graphe (compréhension) et recherche par le sens     existant
├─ langue/              détection de la langue (modèles), lexique tunisien  fait
├─ voix/                voix vers texte, texte vers voix                    fait (Whisper small, Piper)
├─ sources/             URL configurées, lecture hebdomadaire, état         fait
├─ apprentissage/       liste pour l'AFI, exemples vérifiés, noms de lieux  fait (voir son README)
├─ administration/      supervision, connaissances, réglages, droits        à faire
├─ moteurs/             modèles locaux (langage Ollama)                     fait pour le langage
├─ connaissances/       construction de la base (MariaDB, vecteurs, graphe) existant
└─ config.py            réglages (.env)
db/                     migrations SQL, corrections relues, références
ontology/               ontologie OWL, règles SHACL, requêtes de test
frontend/               carte interactive et fenêtre de Dalila              à faire
eval/                   jeux de questions, évaluation, comparaison des modèles
tests/                  tests automatiques : outils et harnais, sources, voix
ajustement/             ajustement de l'agent : jeu d'entraînement, script Kaggle, Modelfile
deploy/                 image Docker, préparation, scripts de la base et d'Ollama (docker-compose.yml à la racine)
scripts/                page de test (tester.bat)
docs/                   architecture, décisions, limites, exigences
donnees/  modeles/      hors git : afi.sql et corpus, modèles téléchargés
```

| Brique | Où | Rôle |
|---|---|---|
| **MariaDB 11.8** | `db/` | Copie des tables de l'AFI (`afi.sql`, rafraîchie depuis la carte publique). Les vues `v_pub_*` lisent **en direct** zones, lots, prix, distances, équipements, services et plans ; les corrections relues (`db/corrections/`) s'y appliquent tant que l'AFI n'a pas changé la valeur. Nos tables `dalila_*` gardent seulement ce que l'AFI n'a pas : textes à citer et leurs vecteurs, gouvernorats, cahiers, groupes, corrections. |
| **Graphe (Oxigraph)** | `ontology/` | Le **sens** : ontologie écrite à la main, faits générés depuis la base (aucun chiffre), règles SHACL, graphes nommés. |
| **Évaluation** | `eval/` | Rappel@5, MRR, chiffres exacts, temps de réponse, sur de vraies questions de visiteurs. |

À lire aussi : **[docs/architecture.md](docs/architecture.md)** (la mécanique, fichier par fichier), **[docs/decisions.md](docs/decisions.md)** (les choix
et leurs preuves), **[docs/limites.md](docs/limites.md)** (ce qui manque), **[docs/exigences.md](docs/exigences.md)** (chaque exigence du cahier des charges, son module et son état), **[docs/reste_a_faire.md](docs/reste_a_faire.md)** (où reprendre), **[db/corrections/DESACCORDS.md](db/corrections/DESACCORDS.md)**
(chaque décision sur les données, avec les deux valeurs).

## Installer (Windows, sans Docker)

1. **MariaDB 11.8** (type `VECTOR`). Charger `afi.sql` **tel quel** dans une base `afi` (utf8mb4).
2. Copier `.env.example` en `.env` et le remplir (connexion, mots de passe des comptes `dalila_ro` et `dalila_rw`).
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

```
.venv\Scripts\python -m dalila.connaissances.migrer           tables dalila_*, agent_*, vues v_pub_*, comptes dalila_ro / dalila_rw
.venv\Scripts\python -m dalila.connaissances.charger          références, corrections, passages (+ réponses AFI et fiches de zone)
.venv\Scripts\python -m dalila.connaissances.construire_abox  graphe : génération, SHACL, OWL RL, Oxigraph, requêtes de test
.venv\Scripts\python -m dalila.connaissances.vectoriser       vecteurs des passages (BGE-M3 par défaut ; --modele e5 ou qwen3 pour les autres)
```

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

## Lancer l'agent (API `POST /carte/chatbot`)

1. **Ollama** (https://ollama.com), puis le modèle de l'agent :
   - **modèle ajusté (par défaut)** : le fichier `dalila.Q4_K_M.gguf` (2,5 Go, sortie du carnet Kaggle privé
     `dalila-ajustement-qwen3-4b`, hors git) dans `donnees/ajustement/modele/`, puis
     `ollama create dalila-qwen3-4b -f ajustement/Modelfile` ;
   - **modèle de base** (utilisé seul si le modèle ajusté n'est pas installé) : `ollama pull qwen3:4b-instruct`.
   `DALILA_LLM` impose l'un ou l'autre.
2. Le service (le premier démarrage lit les consignes une fois : 40 à 60 s sur processeur) :
   ```
   .venv\Scripts\python -m uvicorn dalila.communication.api:app --host 0.0.0.0 --port 8000
   ```
3. `GET /sante` rend `{"pret": true, "base": true}` quand le service est prêt. Exemple :
   ```
   curl -X POST http://localhost:8000/carte/chatbot -H "Content-Type: application/json" ^
        -d "{\"message\": \"lot de 2000 m² à Jendouba\", \"lang\": \"fr\"}"
   ```
   Réponse : `message` (avec les balises `[[ZONE]]`, `[[LOT]]`, `[[CHOIX]]`, `[[PDF]]`), `log_id`, `source`
   (`dalila` ou `repli`), `action` (`choix` si des boutons sont proposés), `duree_s`, `langue` détectée
   (fr, en, ar, de, tr, tn : codes du contrat) et `ecriture` (arabe ou latin). Avis : `POST /carte/chatbot/avis`
   `{"log_id": 12, "utile": true, "commentaire": "facultatif"}`. Documentation interactive : http://localhost:8000/docs.

Étude de projet guidée (10 questions, puis PDF) : `POST /carte/etude` `{session_id, lang}`, ou à la demande du
visiteur dans le chat ; tant qu'elle dure, `/carte/chatbot` reçoit les réponses (même `session_id`) ; le PDF :
`GET /carte/etude/{id}.pdf` (dossier `donnees/etudes/`, hors git).

Voix : `POST /carte/voix/transcrire` (fichier `audio` envoyé par le micro du navigateur, `lang`) rend le texte reconnu,
à afficher puis envoyer à `/carte/chatbot` ; `POST /carte/voix/lire` (`texte`, `lang`) rend la réponse lue (WAV).
Modèles de voix à installer une fois : voir `dalila/voix/README.md`.

Réglages dans `.env` : `DALILA_LLM` (modèle, défaut `qwen3:4b-instruct`), `DALILA_LLM_CPU=1` (processeur seul, comme
le serveur de l'AFI), `DALILA_CORS` (origines autorisées, séparées par des virgules ; défaut `*`).
Les tours sont journalisés anonymisés dans `agent_turns` ; les questions sans réponse fiable dans `agent_needs`.

## Tester

- `.venv\Scripts\python -m tests.traitement.test_outils` : outils et harnais sur de vraies questions (base chargée).
- `.venv\Scripts\python -m tests.voix.test_voix` et `-m tests.sources.test_sources` : voix, sources.
- `.venv\Scripts\python -m eval.voix_bench` : vitesse et exactitude de la voix ; rapport dans `eval/reports/`.
- Page d'essai locale (voix et chat) : http://localhost:8000/essai une fois le service lancé.
- `.venv\Scripts\python -m eval.agent_bench --delai 35` : banc d'essai de l'agent (40 vraies questions, processeur
  seul) ; rapports dans `eval/reports/`.
- `scripts/tester.bat` (double-clic) : pose une question, une page s'ouvre avec ce que Dalila a trouvé.
- `.venv\Scripts\python -m eval.run_eval` : jeu de 30 questions du lexique ; `--questions eval/testset/<fichier>.csv` pour un autre jeu.
- `.venv\Scripts\python -m dalila.langue.lexique.tests.tester_lexique` : tests du lexique tunisien.

## Avec Docker (recommandé)

Une commande depuis la racine, avec `.env` rempli et la base exportée dans `donnees/dalila_base.sql.gz` (et si possible
le modèle ajusté) : tout est expliqué dans **[docs/docker.md](docs/docker.md)**.
```
docker compose up --build -d        puis http://127.0.0.1:8000/
```

## Règles

- Un chiffre (prix, surface, disponibilité, distance) vient **toujours** des vues `v_pub_*`, jamais d'un passage ni du graphe.
- Le compte `dalila_ro` ne lit que les vues publiques : les noms des acquéreurs (`LOT_PROMOTEUR`) et les contrats lui sont inaccessibles.
- Les données de l'AFI ne sont jamais copiées : une correction garde la valeur AFI d'origine et cesse de s'appliquer si l'AFI la change.
- Les libellés non vérifiés (allemand, turc, formes tunisiennes non attestées) sont dans le graphe nommé **a-valider**.
- Lexique : `translitteration_arabizi_tarc.csv` et `variantes_arabizi_tarc.csv` dérivent du corpus TArC (CC BY-NC-SA 4.0) : **démo seulement**.
- `afi.sql`, `dalila_base.sql.gz` et le corpus ne sont jamais dans git ni dans l'image Docker : ils sont montés au lancement.
