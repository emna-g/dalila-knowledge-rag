# Dalila : graphe de connaissances et recherche (ChromaDB)

Code de la partie « données et recherche » de **Dalila**, l'assistante de l'AFI (Agence Foncière Industrielle), pour le Hackathon AGENTIC (novembre 2026).

Trois briques, chacune avec un seul rôle :

| Brique | Fichier | Rôle |
|---|---|---|
| **Chiffres** | `base/dalila.sqlite` (créé par `construire_sqlite.py`) | Prix, surfaces, statuts des lots, distances. **Source unique des chiffres.** |
| **Graphe** | `graphe/dalila.ttl` (créé par `construire_graphe.py`) | Ontologie OWL/RDF, 9 familles de concepts, synonymes multilingues. **Sans prix ni statut.** |
| **Recherche** | `index_chroma/` (créé par `construire_index.py`) | Passages de texte à citer, recherche hybride (sens + mots-clés) avec le lexique tunisien. |

Le détail de chaque fichier et des concepts est dans **[GUIDE_COMPLET.md](GUIDE_COMPLET.md)**.

## Installation

Python 3.10 ou plus récent.

```
python -m pip install --target libs torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
python -m pip install --target libs -r requirements.txt
```

Les bibliothèques vont dans `libs/` et le modèle d'embeddings (multilingual-e5-small, environ 470 Mo) dans `modeles/`. Ces deux dossiers ne sont pas versionnés.

## Données

Les données ne sont pas dans ce dépôt (taille et confidentialité). Il faut télécharger depuis le Drive de l'équipe, dossier « Hackathon Dalila / Pipeline Dalila (graphe + ChromaDB) – 26-11 », les deux fichiers `dalila_fusion_partie1_base_zones_lots.zip` et `dalila_fusion_partie2_textes_passages.zip`. On les décompresse dans `donnees/dalila_fusion/`.

## Construire et tester

```
python construire_sqlite.py --donnees donnees/dalila_fusion --sortie base/dalila.sqlite
python construire_graphe.py --donnees donnees/dalila_fusion --lexique lexique_tunisien --sortie graphe
python construire_index.py  --donnees donnees/dalila_fusion --sortie index_chroma
python evaluer.py
python demo_dalila.py "n7eb terrain f Sfax"
```

`construire_index.py` prend environ 27 minutes sur un processeur.

## Résultats actuels

- **Graphe :** 19 468 faits. Il est cohérent selon le raisonneur owlrl, et une requête SPARQL de test répond pour chaque famille (`graphe/rapport_graphe.json`).
- **Recherche :** la bonne réponse est dans les 5 premiers résultats pour 20 questions sur 30 (16 sur 25 en tunisien). La recherche par le sens seule n'en trouvait que 12 sur 30 (`evaluation/resume.json`).

## Règles

- Un chiffre vient **toujours** de la base SQLite, jamais d'un passage ni du graphe.
- Aucune donnée personnelle dans ce dépôt (les noms d'acquéreurs sont masqués dans les données, qui restent hors du dépôt).
- Lexique : les fichiers `translitteration_arabizi_tarc.csv` et `variantes_arabizi_tarc.csv` sont dérivés du corpus TArC (licence CC BY-NC-SA 4.0, usage non commercial).
