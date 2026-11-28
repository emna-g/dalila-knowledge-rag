# Lancer Dalila avec Docker

Une commande, sur toute machine avec Docker (Docker Desktop sous Windows ou macOS) : la base, le modèle de l'agent,
le service et l'interface. Processeur seul, comme le serveur de l'AFI. Mémoire : au moins **12 Go donnés à Docker**
(Docker Desktop > Settings > Resources ; sous Windows avec WSL 2 : `memory=12GB` dans `%UserProfile%\.wslconfig`), car
le modèle de l'agent et ceux de la voix et de la recherche tiennent ensemble en mémoire.

## 1. Une fois

1. Cloner le dépôt, se placer à sa racine.
2. `.env` : copier `.env.example` en `.env` et remplir les trois mots de passe (`DB_ROOT_PASSWORD`, `DB_RO_PASSWORD`,
   `DB_RW_PASSWORD` ; au choix, ils ne servent que sur la machine). Jamais dans git.
3. `donnees/` : y mettre ces **trois fichiers**, reçus d'un membre de l'équipe par un moyen privé (jamais dans git ni
   dans l'image : le dépôt est public, la base contient les tables de l'AFI, dont les noms des acquéreurs) :

   | Fichier | Rôle | Obligatoire |
   |---|---|---|
   | `donnees/dalila_base.sql.gz` (86 Mo) | notre base MariaDB exportée (`deploy/exporter_base.sh`) : tables de l'AFI, textes à citer **et leurs vecteurs** | oui |
   | `donnees/ajustement/modele/dalila.Q4_K_M.gguf` (2,5 Go) | le modèle de l'agent (ajusté sur Kaggle) | oui : sans lui, `ollama` refuse de démarrer |
   | `donnees/langue_latin.joblib` (4 Mo) | la détection de la langue des messages en lettres latines (celle qui a été mesurée) | oui |

   Rien d'autre : le code, l'ontologie, le lexique, les références et les corrections sont dans le dépôt ; les autres
   modèles (recherche, voix, langue arabe, noms) sont publics et téléchargés au premier lancement.

## 2. Lancer

```
docker compose up --build -d
```

puis ouvrir **http://127.0.0.1:8000/**.

Le premier lancement est long (de 20 à 40 minutes selon la connexion) : construction de l'image, chargement de la
base, téléchargement de l'image d'Ollama (≈ 9 Go) et des modèles (≈ 6 Go : recherche, voix, langue, noms), construction du graphe, installation du
modèle de l'agent. Tout est gardé dans des volumes Docker : les lancements suivants prennent une minute environ
(préchauffage des modèles). Suivre l'avancement :

```
docker compose logs -f preparer ollama dalila
```

Une fois lancé, créer le compte de l'administrateur (mot de passe demandé deux fois, au moins 12 caractères) :

```
docker compose exec dalila python -m dalila.communication.comptes creer admin --role admin --nom "Agent AFI"
```

puis se connecter sur http://127.0.0.1:8000/connexion/ (bouton « Connexion » de la carte) : l'administrateur arrive
sur l'administration (`/admin/`).

`dalila` démarre quand `preparer` a fini (« prêt ») et qu'Ollama a son modèle. http://127.0.0.1:8000/sante répond dès
que le service est prêt.

## 3. Ce qui tourne

| Service | Rôle |
|---|---|
| `db` | MariaDB 11.8 (type `VECTOR`) ; au premier démarrage, charge `dalila_base.sql.gz` (ou `afi.sql`). Port 33062 de la machine pour les outils (`DB_PORT_HOTE` dans `.env` pour le changer). |
| `ollama` | le modèle de l'agent : installe le modèle ajusté de `donnees/` au premier démarrage, et refuse de démarrer s'il manque. |
| `preparer` | une fois par lancement, puis s'arrête : tables, vues et comptes (`migrer`), textes à citer (`charger`), vecteurs manquants, graphe, modèles. Chaque étape déjà faite est sautée. |
| `dalila` | l'API (`/carte/chatbot`, `/carte/voix/…`, `/carte/etude`, `/carte/demande`, `/sante`), l'interface de la carte (`/`) et l'administration (`/admin/`), sur le port 8000. |

Volumes : `base` (MariaDB), `ollama` (modèle de l'agent), `modeles` (modèles téléchargés), `graphe` (graphe construit).

## 4. Commandes utiles

| Pour | Commande |
|---|---|
| arrêter / relancer | `docker compose down` / `docker compose up -d` |
| après un `git pull` | `docker compose up --build -d` |
| reconstruire le graphe (après un apprentissage publié) | `docker compose run --rm preparer python -m deploy.preparer --graphe` puis `docker compose restart dalila` |
| un cycle d'apprentissage | `docker compose run --rm preparer python -m dalila.apprentissage.synonymes_appris` (idem `lieux_appris`) |
| les tests | `docker compose run --rm preparer python -m tests.traitement.test_outils` (et les autres fichiers de `tests/`) |
| l'évaluation | `docker compose run --rm preparer python -m eval.agent_bench` |
| comptes : nouveau mot de passe, désactiver, lister | `docker compose exec dalila python -m dalila.communication.comptes mot-de-passe admin` (`desactiver admin`, `lister`) |
| repartir de zéro (efface la base, les conversations et les modèles téléchargés) | `docker compose down -v` |

## 5. Cas particuliers

- **Sans `dalila_base.sql.gz`, avec `afi.sql` et le corpus préparé (`donnees/corpus/`)** : la base est construite à
  partir d'eux et les vecteurs des 8 858 textes sont calculés : plusieurs heures sur processeur, une seule fois.
- **Carte graphique NVIDIA** : inutile pour la démonstration. Pour l'agent, ajouter sous le service `ollama` du
  `docker-compose.yml` : `deploy: {resources: {reservations: {devices: [{driver: nvidia, count: all, capabilities: [gpu]}]}}}`
  et mettre `DALILA_LLM_CPU=0` dans `.env`.
- **Ollama déjà installé sur la machine** : on peut garder le service `ollama` (rien à faire) ; il est séparé de celui de
  la machine.
- **Port 8000 déjà pris** : changer `"127.0.0.1:8000:8000"` en `"127.0.0.1:8080:8000"` dans `docker-compose.yml`.
- **Micro du navigateur** : il marche sur http://127.0.0.1 ; sur une autre adresse, il faut HTTPS (BNF9).

## 6. Refaire `dalila_base.sql.gz` (après une mise à jour de la base)

Depuis une base à jour (tables de l'AFI, `charger` et `vectoriser` passés) ; sans les conversations (`agent_*`) ni les
vues (recréées par `migrer`) :

```
sh deploy/exporter_base.sh
```
