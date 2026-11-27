# Module traitement (outils de l'agent)

Les outils que l'agent appelle. Liste fermée (`registre.py`) : un outil absent du registre ne peut pas être appelé.
Chaque outil a une entrée et une sortie typées (Pydantic), effectue des lectures avec le compte `dalila_ro` sur les
vues AFI et les tables DALILA autorisées, et rend ses sources. Les temps de réponse des passages dépendent du modèle.

| Outil | Fichier | Rôle | Exigences |
|---|---|---|---|
| `resoudre_lieu` | `lieux.py` | Nom de lieu → zone, gouvernorat ou région (fautes, arabe, anciens noms) ; ambigu ou trop vague : l'agent pose une question à choix | BF2, BF4 |
| `chercher_lots` | `lots.py` | Lots disponibles : lieu, surface, prix au m², budget, régime, groupe, proximité ; nombre exact + les moins chers | BF4, BF10, BNF1 |
| `fiche_zone` | `zones.py` | Prix, surfaces, lots, régime et groupe, distances, équipements, services, cahier des charges, plan | BF4 |
| `lister_zones` | `zones.py` | Zones d'un lieu, d'un régime ou d'un groupe | BF4 |
| `zones_proches` | `zones.py` | Zones proches d'un aéroport, port, gare, autoroute, gazoduc | BF4 |
| `demarche` | `services.py` | Les 8 services de l'AFI : liste pour guider, puis conditions, pièces, frais, étapes, lien, contact | BF22, BF23, BF24 |
| `chercher_passages` | `passages.py` | Textes officiels à citer (cahiers des charges, incitations, sites officiels) | BF14, BF17 |

```python
from dalila.traitement.registre import definitions, appeler
definitions()                                         # schémas pour les appels d'outils d'Ollama
appeler("resoudre_lieu", {"texte": "Grand Tunis"})    # -> région, 4 gouvernorats
appeler("chercher_lots", {"gouvernorats": [9], "surface_min_m2": 2000})
```

Les tests unitaires hors base sont dans `tests/`. `tests/traitement/test_outils.py` est une intégration réelle :
elle est ignorée par défaut et exige une base de test isolée préfixée `dalila_test_`, les migrations ciblées, les
références, le corpus et l'ontologie initialisés. Définir `DALILA_TEST_DB_NAME` sur ce schéma avant de lancer ce test;
le module refuse les noms sans préfixe et remplace explicitement `DB_NAME` pour éviter de toucher à la base du `.env`.

**À faire :** regroupement de lots voisins pour une grande surface (comme la recherche de terrain de l'application
actuelle) ; préparation d'une demande d'acquisition (BF11, brouillon jamais déposé sans confirmation) ; qualification
et étude de projet (BF4). `outils.py` est l'adaptateur historique encore utilisé par `harnais/pipeline_fixe.py`,
notamment par `scripts/tester.py` et `eval/run_eval.py`; ne pas le supprimer avant la migration de ces consommateurs.
