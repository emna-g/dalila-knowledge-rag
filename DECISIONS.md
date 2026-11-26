# Décisions prises sur cette branche (refonte-revue-1-12)

Chaque décision suit un point de la revue de l'équipe. Les chiffres viennent des contrôles de la branche (26/11/2026).

| Point | Décision | Preuve |
|---|---|---|
| 1 | **MariaDB 11.8 LTS** comme source unique ; `afi.sql` chargé tel quel ; nos tables à côté. Installée en version zip sur D: (pas de Docker pour l'instant). | Les vues donnent 680 lots disponibles, et 159 / 76 / 57 pour Gabès, Om Laatham et Sejnane. `dalila_ro` ne peut pas lire `lots.LOT_PROMOTEUR`. |
| 2 | **Passages et vecteurs dans MariaDB** (colonne `VECTOR`, distance `VEC_DISTANCE_COSINE`, recherche exacte), ChromaDB abandonné. Pour une base 10.11 : colonne `BLOB` et calcul numpy. | 8 860 passages chargés, 227 doublons exacts écartés. Score de recherche identique à l'ancienne version (19/30), en 0,4 s par question. |
| 3 | **Une seule source par chiffre** : comptes calculés par les vues ; plus de distance ni de prix dans le graphe. | Règle SHACL `PasDeChiffresMetier` : 0 violation. |
| 4 | **Ontologie écrite à la main** (`ontology/dalila.ttl`) ; faits générés depuis la base (`construire_abox.py`). | |
| 5 | **SHACL** (pyshacl) à chaque construction ; OWL RL (owlrl) en plus. | SHACL conforme ; OWL RL : 0 erreur ; une erreur volontaire (lot et organisme à la fois) est bien détectée. |
| 6 | **8 langues** : les traductions que personne n'a vérifiées sont isolées dans le graphe nommé `a-valider`. | fr, en, ar, de, tr, aeb, arq, ayl présents sur les 9 familles ; de/tr/arq/ayl **à valider**. |
| 7 | **Familles remplies depuis des sources réelles uniquement** : fiches AFI 12 à 25 (procédures, étapes, pièces, frais), TIA (11 avantages des zones 1 et 2), nomenclature de l'APII (17 secteurs, 484 activités). | Chaque fait porte `dcterms:source` (contrôlé par SHACL). |
| 8 | **Erreurs de modélisation corrigées** : `Document` séparé de `Démarche` ; `Équipement`, `Infrastructure` et `Service proche` séparés ; « usine » → nature du projet, « papiers » → pièce à fournir ; plus d'exception de disjonction. | |
| 9 | **Oxigraph embarqué** (`pyoxigraph`), graphes nommés `core`, `abox`, `lexique`, `a-valider`, `appris/<id>`. | 11 requêtes de test (une par famille, plus BF17 et BF20) répondent. |
| 10 | **BGE-M3 + reranker (bge-reranker-v2-m3) deviennent le réglage par défaut** (décision d'Emna, 26/11), conformément à la revue. Le calcul des vecteurs et la comparaison avec e5 sont **confiés à un PC plus puissant** : sur le PC d'Emna (4 cœurs), BGE-M3 prend environ 1,5 s par passage. e5-small reste disponible comme modèle léger (`DALILA_MODELE=e5`). | Mesure : 16 passages en 29 s à 256 jetons (108 s à 512). Les chiffres de la comparaison restent à produire (README, « Lancer sur un PC puissant »). |
| 11 | **Recherche guidée par le graphe** : zone reconnue → seulement le cahier des charges de cette zone ; régime de la zone → fiches AFI du bon régime ; service reconnu → ses fiches officielles en tête ; langue de la question en premier ; fiche de zone avec ses commodités. Noms de zones longs et petites fautes reconnus. | Cas Sidi Achour : zone, commodités, 11 services proches trouvés. |
| 12 | **Jeu de test** : modèle à remplir par l'équipe (`eval/testset/MODELE_questions.csv`) ; 24 questions d'exemple dans les 8 langues, **écrites par Claude, à relire**, qui ne comptent pas dans le score officiel. | Sur ces 24 : 16/16 passages trouvés, 8/8 chiffres exacts. Jeu facile, écrit par l'IA : à remplacer par les questions de l'équipe. |

## Comparaison rapide sur un échantillon (point 10, facultatif)

```
.venv\Scripts\python -m backend.ingest.echantillon --taille 1500
.venv\Scripts\python -m backend.ingest.vectoriser --modele bge --echantillon --lot 16 --longueur-max 256
.venv\Scripts\python -m eval.run_eval --modele e5  --echantillon
.venv\Scripts\python -m eval.run_eval --modele bge --echantillon
.venv\Scripts\python -m eval.run_eval --modele bge --echantillon --reranker
```
Les 3 réglages sont comparés sur le même échantillon. Choisir le meilleur qui reste sous le budget de temps de réponse, puis mettre `DALILA_MODELE=bge` dans `.env` (et vectoriser tout l'index).

## Reporté

- Point 13 : Docker Compose. Point 14 : partage du Drive.
- Point 10 : vecteurs BGE-M3 et comparaison chiffrée, à lancer sur un PC puissant.
