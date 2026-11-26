# Dalila : base de connaissances et recherche (version MariaDB + Oxigraph)

Partie « données et recherche » de **Dalila**, l'assistante de l'AFI (Agence Foncière Industrielle), Hackathon AGENTIC 2026.
Cette branche (`refonte-revue-1-12`) applique les points 1 à 12 de la revue de l'équipe (`docs` : « 14 — Review of the data/RAG pipeline »).

| Brique | Où | Rôle |
|---|---|---|
| **MariaDB 11.8** | `db/migrations/` | **Source unique des chiffres et des textes.** `afi.sql` est chargé **tel quel** ; nos tables `dalila_*` et `agent_*` sont ajoutées à côté ; la carte et Dalila lisent les mêmes vues `v_pub_*`. Les passages et leurs vecteurs (type `VECTOR`) y sont aussi : ChromaDB n'est plus utilisé. |
| **Graphe (Oxigraph)** | `ontology/` | Le **sens** : ontologie OWL écrite à la main (`dalila.ttl`), données générées depuis la base (aucun prix, statut ni distance), contrôles SHACL (`shapes.ttl`), graphes nommés (core, abox, lexique, a-valider, appris/…), requêtes de test (`queries/*.rq`). |
| **Recherche** | `backend/app/` | Comprendre la question avec le graphe, lire les chiffres dans les vues, trouver les passages à citer (filtres SQL + sens + mots-clés). |
| **Lexique tunisien** | `lexicon/` | Comprendre l'arabizi et la darija (formes attestées seulement). |
| **Évaluation** | `eval/` | Mesures (rappel@5, MRR, chiffres exacts, temps) et modèle de jeu de test pour l'équipe. |

Les explications fichier par fichier sont dans **[GUIDE_COMPLET.md](GUIDE_COMPLET.md)**, et les choix chiffrés dans **[DECISIONS.md](DECISIONS.md)**.

## Installer (Windows, sans Docker)

1. **MariaDB 11.8** en version zip (sans installateur ni service) :
   ```
   mariadb-install-db.exe --datadir=<dossier>\data --password=<mot de passe root> --port=3307
   mariadbd.exe --defaults-file=<dossier>\data\my.ini --console
   ```
2. **Charger `afi.sql` tel quel** dans une base `afi` (utf8mb4), puis copier `.env.example` en `.env` et le remplir.
3. **Python** dans un environnement virtuel :
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
4. **Données** : décompresser les 2 zips `dalila_fusion_partie*.zip` du Drive d'équipe dans `donnees/dalila_fusion/`.

## Construire (dans l'ordre)

```
.venv\Scripts\python -m backend.ingest.migrer           tables dalila_*, agent_*, vues v_pub_*, comptes dalila_ro / dalila_rw
.venv\Scripts\python -m backend.ingest.charger_fusion   remplit les tables depuis dalila_fusion (doublons écartés)
.venv\Scripts\python -m backend.ingest.vectoriser --modele e5     vecteurs des passages (environ 25 min)
.venv\Scripts\python -m backend.ingest.construire_abox  graphe : génération, SHACL, OWL RL, Oxigraph, requêtes de test
```

## Tester

- `tester.bat` (double-clic) : pose une question, une page s'ouvre avec ce que Dalila a trouvé.
- `.venv\Scripts\python -m eval.run_eval` : jeu de 30 questions ; `--questions eval/testset/<fichier>.csv` pour un autre jeu.

## Règles

- Un chiffre (prix, surface, disponibilité, distance) vient **toujours** des vues MariaDB, jamais d'un passage ni du graphe.
- Le compte `dalila_ro` ne lit que les vues publiques : les noms des acquéreurs et les contrats lui sont inaccessibles.
- Les libellés que personne n'a encore vérifiés (allemand, turc, algérien, libyen, formes tunisiennes non attestées) sont dans le graphe nommé **a-valider**.
- Lexique : `translitteration_arabizi_tarc.csv` et `variantes_arabizi_tarc.csv` dérivent du corpus TArC (CC BY-NC-SA 4.0) : **démo seulement**.
- Pas de Docker pour l'instant (point 13 de la revue reporté). Ancienne version SQLite + ChromaDB : `ancien_sqlite_chroma/`.
