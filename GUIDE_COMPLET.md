# Guide complet : les données et la mécanique de Dalila

Ce guide explique, fichier par fichier, ce qu'il y a dans les trois dossiers et comment ils travaillent ensemble.

| Dossier | Rôle |
|---|---|
| `donnees/dalila_fusion` (à télécharger depuis le Drive) | **Les données** (ce qu'on sait) |
| `lexique_tunisien/` | **Le tunisien** (comprendre l'arabizi et la darija) |
| la racine de ce dépôt | **La mécanique** (base des chiffres, graphe, index de recherche, tests) |

---

## 1. Les concepts, en une ligne chacun

| Mot | Sens simple |
|---|---|
| **SQLite** | Une base de données dans **un seul fichier**, sans serveur à installer. Python la lit directement. On y met tous les **chiffres**. |
| **Ontologie** | La liste des **types de choses** du domaine (zone, lot, secteur, service…) et de leurs liens (« une zone est dans un gouvernorat »). |
| **Graphe de connaissances** | Les **faits réels** rangés selon l'ontologie : « Sejnane est dans le gouvernorat de Bizerte », « la pêche relève de l'APIA ». |
| **RDF / OWL / Turtle** | Les formats standards du graphe. RDF écrit chaque fait en 3 morceaux (sujet, lien, objet). OWL décrit l'ontologie. Turtle est le fichier texte qui les contient. |
| **SPARQL** | Le langage pour interroger le graphe (comme SQL, mais pour un graphe). |
| **Raisonneur (owlrl)** | Un programme qui vérifie que le graphe ne se contredit pas (par exemple, une chose ne peut pas être à la fois un lot et un organisme). |
| **Synonymes avec langue** | Pour chaque concept, ses mots dans chaque langue : `terrain`@fr, `plot`@en, `أرض`@ar, `9at3a`@aeb-Latn. « aeb » est le code officiel du tunisien. |
| **Embedding** | Une liste de nombres qui résume le **sens** d'un texte. Deux textes de même sens ont des listes proches, même dans des langues différentes. |
| **Modèle e5** | Le programme qui fabrique les embeddings (`multilingual-e5-small`) : gratuit, multilingue (FR, AR, EN…), tourne sur le processeur. |
| **ChromaDB** | La base qui garde les embeddings des passages et retrouve en une fraction de seconde ceux qui sont **les plus proches** d'une question. |
| **RAG** | Le LLM cherche d'abord les passages utiles (dans ChromaDB), puis rédige sa réponse **à partir d'eux**, en citant la source. Il ne répond pas de mémoire. |
| **Arabizi** | Le tunisien écrit en lettres latines et en chiffres : 3 = ع, 7 = ح, 9 = ق, 5 = خ (« n7eb » = نحب, « je veux »). |
| **Normalisation** | Reconnaître qu'un message est en tunisien et y ajouter les mots équivalents en français et en arabe standard, pour que la recherche le comprenne. |

**Règle d'or :** un **chiffre** (prix, surface, disponibilité) vient toujours de la base SQLite. Le graphe donne le **sens** et les liens. Les passages donnent les **explications** à citer.

---

## 2. Le trajet d'une question

Exemple : un visiteur écrit **« chnowa lwra9 lazmin bech na5ou ma9sem sina3i? »** (« quels papiers faut-il pour prendre un lot industriel ? »).

1. **Lexique** (`normaliser.py`) : il reconnaît du tunisien, puis trouve les idées *quoi, papiers, falloir, prendre, terrain, industriel*. Il ajoute à la question « papiers وثائق terrain قطعة أرض industriel… ».
2. **Graphe** (`dalila.ttl`) : « ma9sem » est un synonyme du concept **Lot**, et « papiers » mène à **Démarche**. Le graphe relie la démarche **Acquisition** aux fiches 12 à 17 de l'AFI.
3. **ChromaDB** (`rechercher.py`) : la question enrichie devient un embedding. ChromaDB renvoie les 5 passages les plus proches, par exemple la fiche « documents à fournir pour acheter un lot » et le formulaire de demande d'acquisition, chacun avec son lien.
4. **Chiffres** (`chiffres.py`) : si la question parle d'un lieu ou d'une surface (« n7eb terrain f Sfax »), Dalila lit les lots disponibles à Sfax dans SQLite, avec le prix au m² et la surface.
5. **LLM** : il rédige la réponse dans la langue du visiteur, avec les passages et les chiffres reçus, et cite les sources. S'il ne trouve rien, il le dit et donne le contact de l'AFI.

---

## 3. `dalila_fusion` : les données

| Fichier ou dossier | Ce qu'il contient | À quoi il sert |
|---|---|---|
| `LISEZMOI.md` | Ce qui a changé avec la fusion et le guide des dossiers. | À lire en premier. |
| `MANQUES_ET_ALERTES.md` | Ce qui manque ou se contredit (14 zones sans cahier, contradictions…). | Savoir quand Dalila doit dire « je ne sais pas ». |
| `rapport_fusion.json`, `rapport_qualite.json` | Les chiffres et contrôles de la fusion et du nettoyage. | Prouver la qualité au jury. |
| `0_base_afi_complete/` | Les 13 tables de `afi.sql`, ligne par ligne, avec les noms d'acquéreurs et les identifiants masqués. | Archive complète ; rien n'est perdu. |
| `1_zones_et_lots/zones.json` | 52 zones : noms FR/AR, gouvernorat, GPS, prix au m², distances, équipements, nombre de lots par statut. | Source de la base SQLite et du graphe. |
| `1_zones_et_lots/lots.json` | 3 172 lots : numéro, surface, **statut** (disponible, réservé, attribué, mis aux enchères…), `a_confirmer`. | Source des chiffres des lots. Exemple : lot 5111, Menzel Chekir, 2 398 m², disponible. |
| `1_zones_et_lots/lots_polygones*.geojson` | Les contours des lots (anciennes et nouvelle carte). | Dessiner les lots sur la carte. |
| `1_zones_et_lots/releve_nouvelle_carte_lots.jsonl` | 153 lots lus sur la nouvelle carte carte.afi.nat.tn (3 zones). | Vérifier les statuts. |
| `1_zones_et_lots/services_proches.json`, `gouvernorats.json` | Les services OpenStreetMap près de chaque zone (banque, hôpital…) ; les 23 gouvernorats. | Réponses « qu'y a-t-il près de la zone ? ». |
| `2_cahiers_des_charges/` | `index.csv` et le texte des 61 cahiers des charges (règles par zone). | Répondre à « quelles activités sont permises dans cette zone ? ». |
| `3_connaissances_afi/` | Les 85 réponses validées par l'AFI et les 150 extraits de sites de la base. | Les réponses les plus fiables. |
| `4_sites_officiels/pages_web.jsonl` | Les 984 pages des sites AFI, APII, TIA et FIPA. | Explications à citer. |
| `5_documents/` | Le texte de 79 PDF (lois, formulaires, guides). | Explications à citer. |
| `6_pret_pour_le_llm/passages.jsonl` | **9 087 passages courts**, dont 8 966 à indexer, chacun avec sa source, sa date, `doublon_de` et `contient_chiffre`. | **Ce qu'on met dans ChromaDB.** |
| `7_conversations_ancien_bot/` | 214 vraies questions de visiteurs (anonymisées), dont 53 mal traitées. | Jeu de test. |
| `base_mariadb/` | `schema.sql` et `donnees.sql` pour MariaDB. | **Pas utilisé** (choix d'Emna : pas de MariaDB). Gardé pour un branchement plus tard. |
| `controles/` | 75 lots à confirmer, lots où base et carte diffèrent, 19 conflits entre sources, registre des sources. | Liste des vérifications à faire avant la démo. |
| `outils/` | Les scripts qui ont produit ce dossier. | Tout refaire si les sources changent. |

---

## 4. `lexique_tunisien` : comprendre le tunisien

| Fichier | Ce qu'il contient | À quoi il sert |
|---|---|---|
| `LISEZMOI.md` | Comment le lexique a été construit et testé. | Comprendre et défendre le lexique. |
| `lexique_tunisien.csv` | 66 idées (terrain, prix, papiers, port…) : mots français, anglais, arabe standard, tunisien, arabizi. Les formes non prouvées sont dans une colonne à part. | Lecture humaine (Excel) et relecture par un Tunisien. |
| `lexique_tunisien.json` | Le même lexique pour le code, avec pour chaque mot sa preuve (où il a été vu) et son statut. | Utilisé par `normaliser.py` et par le graphe (synonymes). |
| `correspondance_arabizi.csv` | Quel chiffre remplace quelle lettre (3 = ع à 99 %, 7 = ح, 9 = ق…), mesuré sur un vrai corpus. | Écrire l'arabizi en lettres arabes. |
| `translitteration_arabizi_tarc.csv`, `variantes_arabizi_tarc.csv` | 11 500 mots arabizi avec leur écriture arabe, et les orthographes vues pour chaque mot. | Reconnaître les orthographes variées (« kifech », « kifach »…). |
| `outils/normaliser.py` | Le module qui analyse un message : est-ce du tunisien ? quelles idées ? quelle requête envoyer à la recherche ? | Appelé avant chaque recherche. |
| `outils/construire_lexique.py`, `candidats.py` | La liste de départ et le script qui vérifie chaque mot dans les corpus. | Refaire le lexique après relecture. |
| `sources/` | Les corpus publics de tunisien (TArC, TUNIZI, TSAC) et leurs licences. | Preuves des mots. |
| `tests/` | 32 questions de test et leurs résultats. | Mesurer ce que le lexique apporte. |

---

## 5. `dalila_pipeline` : la mécanique

| Fichier ou dossier | Ce qu'il contient | À quoi il sert |
|---|---|---|
| `construire_sqlite.py` | Lit `dalila_fusion` et crée `base/dalila.sqlite`, avec les mêmes tables et vues `v_pub_*` que le schéma MariaDB. | Créer la base des chiffres. |
| `base/dalila.sqlite` | 52 zones, 3 172 lots (680 disponibles, dont 75 à confirmer), distances, équipements, services, cahiers, 85 réponses AFI. | **Source unique des chiffres.** |
| `chiffres.py` | Fonctions prêtes : `chercher_lots(gouvernorat, surface_min, surface_max, prix_max_m2)`, `zone(id)`, `zones_proches("port", 10)`. | Ce que l'agent appelle pour donner un chiffre. Exemple : lots disponibles à Sfax, du moins cher au plus cher. |
| `construire_graphe.py` | Écrit l'ontologie (9 familles), ajoute les faits (gouvernorats, zones, liens vers les lots, distances, cahiers, organismes, secteurs, démarches, 8 services AFI), ajoute les synonymes du lexique, puis vérifie la cohérence et lance 10 requêtes de test. | Créer le graphe (BF16, BF17, BNF19). |
| `graphe/dalila.ttl` | Le graphe : 19 468 faits, **sans prix ni statut**. | Comprendre le sens et relier les concepts. Exemple : « 9at3a », « أرض », « plot » et « terrain » mènent au concept Lot. |
| `graphe/rapport_graphe.json` | Nombre de faits, résultat du raisonneur (cohérent), résultat des 10 requêtes SPARQL. | Preuve pour BNF19. |
| `construire_index.py` | Transforme les 8 966 passages à indexer en embeddings (modèle e5) et les range dans ChromaDB avec leurs métadonnées. | Créer l'index de recherche. |
| `index_chroma/` | La base ChromaDB (fichiers internes). | Recherche par le sens. |
| `rechercher.py` | La recherche **hybride** : lexique tunisien, puis deux recherches (par le sens avec ChromaDB, par les mots-clés avec BM25), fusionnées. Elle écarte les passages secondaires ou très courts (mentions légales, menus), favorise les réponses validées par l'AFI et garde au plus 2 passages par page. En ligne de commande : `python rechercher.py "n7eb terrain f Sfax"`. | Ce que l'agent appelle pour trouver le texte à citer. |
| `demo_dalila.py` | Montre ce que le LLM recevrait pour une question : idées du lexique, concepts du graphe, chiffres de SQLite, passages à citer. | Démo devant le jury. Exemples dans `evaluation/demo_exemple.txt`. |
| `evaluer.py` | Pose les 30 questions de test qui ont une réponse attendue, sous 4 réglages, et compte combien trouvent le bon passage dans les 5 premiers. | Mesurer la qualité de la recherche. |
| `evaluation/` | `resultats.csv` (question par question), `resume.json` (les scores) et `demo_exemple.txt`. | Montrer les résultats au jury. |
| `requirements.txt` | La liste des bibliothèques à installer. | Installer le tout sur un autre PC. |
| `libs/`, `modeles/` | Les bibliothèques Python et le modèle e5, installés sur D:. | Faire tourner le tout sans toucher au disque C:. |
| `GUIDE_COMPLET.md` | Ce guide. | |

---

## 6. Résultats de l'évaluation

30 questions avec une réponse attendue (25 en tunisien, dont 6 vraies et 19 écrites pour le test, à faire relire). On compte les questions dont la bonne réponse est dans les 5 premiers passages.

| Réglage | Toutes | Tunisien |
|---|---|---|
| Recherche par le sens seule, sans lexique | 12/30 | 9/25 |
| Recherche par le sens seule, avec lexique | 12/30 | 9/25 |
| Hybride (sens + mots-clés) + filtres, sans lexique | 17/30 | 13/25 |
| **Hybride + filtres + lexique** (réglage retenu) | **20/30** | **16/25** |

**Ce qu'on en retient :**
- La recherche par le sens seule était gênée par des passages vides de sens (mentions légales, plans du site) qui « ressemblent à tout ». Les filtres et les mots-clés corrigent cela.
- Le lexique n'aide que si la recherche par mots-clés est active : il ajoute surtout des mots (« papiers », « terrain », « قطعة أرض »).
- Une partie des échecs restants sont des questions de **chiffres** (« le moins cher », « près de l'aéroport », « eau et électricité ») : elles se règlent avec `chiffres.py` et le graphe, pas avec les passages. C'est voulu.
- Ce jeu de test est petit et en partie écrit pour l'occasion : le jury apportera ses propres questions.

## 7. Ce que chaque brique couvre dans le cahier des charges

| Besoin | Brique |
|---|---|
| BF16 : ontologie OWL/RDF, 9 familles, synonymes | `graphe/dalila.ttl` |
| BF17 : comprendre par le sens | graphe (synonymes) + ChromaDB (embeddings) |
| BNF19 : Turtle rechargeable, raisonneur sans incohérence, une requête par famille | `graphe/rapport_graphe.json` |
| BF1, BF2 : tunisien et arabizi | `lexique_tunisien` + `normaliser.py` |
| BF4, BF6 : chercher un terrain sans inventer | `chiffres.py` (SQLite) |
| BF14 : répondre avec la source | métadonnées des passages (`source_url`, `date_source`) |

**Limites :** pas encore d'algérien ni de libyen ; l'allemand et le turc n'existent que pour les noms des 9 familles ; 175 formes tunisiennes attendent la relecture d'un locuteur.

## 8. Tout relancer (dans l'ordre)

```
python construire_sqlite.py --donnees donnees/dalila_fusion --sortie base/dalila.sqlite
python construire_graphe.py --donnees donnees/dalila_fusion --lexique lexique_tunisien --sortie graphe
python construire_index.py  --donnees donnees/dalila_fusion --sortie index_chroma     (environ 27 minutes)
python evaluer.py
python demo_dalila.py "n7eb terrain f Sfax"
```
