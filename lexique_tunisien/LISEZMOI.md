# Lexique tunisien de Dalila

Ce dossier aide Dalila à comprendre un investisseur qui écrit en tunisien, en lettres arabes (« نحب مقسم ») ou en arabizi (« n7eb ma9sem »). Pour chaque idée utile (terrain, prix, papiers, usine, près du port…), il donne les mots tunisiens, leurs orthographes, et l'équivalent en français et en arabe standard.

**Règle de base : rien n'est inventé.** Chaque mot porte la preuve de l'endroit où on l'a vu. Un mot vu nulle part reste dans le fichier, mais il est marqué « à valider par un locuteur ».

---

## 1. Ce qu'on a trouvé dans nos données

Il y a très peu de tunisien dans les données de l'AFI. Sur les 214 questions des visiteurs de l'ancien Dalila, **seules 2 sont en tunisien** (même visiteur, 27/10/2026) :
- « slt, nheb na3mel usine mta3 plastique fi Sousse, kifech nebda? »
- « chnowa lwra9 lazmin bech na5ou ma9sem sina3i? »

Le cahier des charges officiel du hackathon cite aussi quelques exemples : « n7eb terrain f Sfax », « 3andi projet sardine », « عندي مشروع سردين » (page 7), « terrain / plot / أرض / 9at3a » (page 8) et la règle 3 = ع, 7 = ح, 9 = ق (page 20).

C'est trop peu pour un lexique. On a donc vérifié les mots dans **3 corpus publics de vrais textes tunisiens** (commentaires, forums, blogs) :

| Corpus | Contenu | Licence |
|---|---|---|
| TArC | 43 000 mots d'arabizi tunisien, chacun réécrit en lettres arabes | CC BY-NC-SA 4.0 (usage non commercial : OK pour le hackathon) |
| TUNIZI | 3 000 commentaires en arabizi (iCompass) | pas de licence écrite dans le dépôt : à citer |
| TSAC | 17 000 commentaires tunisiens, lettres arabes et latines | LGPL-3.0 |

Les copies sont dans `sources/`. Pour l'arabe standard, on a vérifié les mots dans les 900 passages en arabe des sites officiels (AFI, APII, TIA, FIPA) du dataset final.

## 2. Comment le lexique a été construit

1. J'ai écrit une liste de départ de **66 idées** et de **498 formes tunisiennes** (fichier `outils/candidats.py`). Elle vient de ma connaissance générale du tunisien, donc elle doit être vérifiée.
2. Le script `outils/construire_lexique.py` cherche chaque forme dans les sources ci-dessus et compte combien de fois elle apparaît.
3. Il ajoute 15 orthographes arabizi **réellement vues** dans TArC (par exemple « bich » pour باش, « shniya » pour شنية), soit 513 formes au total.
4. Chaque forme reçoit un statut :

| Statut | Sens | Nombre de formes |
|---|---|---|
| `vu_conversations_afi` | dans une vraie question d'un visiteur de Dalila | 37 |
| `vu_cahier_des_charges_afi` | cité dans le cahier des charges officiel | 8 |
| `vu_corpus_public` | vu au moins 3 fois dans TArC, TUNIZI ou TSAC | 196 |
| `vu_textes_afi_seulement` | mot arabe vu dans les textes officiels, rien ne prouve qu'il est tunisien | 25 |
| `rare_corpus_public_a_valider` | vu 1 ou 2 fois seulement | 72 |
| `a_valider_locuteur` | vu nulle part : connaissance générale, à faire valider | 175 |

Par idée : **18 sont attestées dans les données de l'AFI**, **31 dans les corpus publics**, et **17 restent à valider** (zone industrielle, usine, dépôt, port, aéroport, gare, électricité, payer, crédit, avantages, louer, autorisation, cahier des charges, enchères, plastique, textile, emballage). Pour ces 17, Dalila comprend déjà le mot français que les Tunisiens mélangent (« usine », « port », « zone »…), mais les formes purement tunisiennes (« mosna3 », « ma3mel », « batta »…) n'ont été vues dans aucune source.

## 3. Les fichiers

| Fichier | À quoi il sert |
|---|---|
| `lexique_tunisien.csv` | Le lexique lisible dans Excel : une ligne par idée, les formes attestées, puis les formes à valider dans une colonne à part. |
| `lexique_tunisien.json` | Le même lexique pour le code et le RAG, avec pour chaque forme son statut, ses comptes par source et un exemple réel. |
| `correspondance_arabizi.csv` | Quel chiffre remplace quelle lettre, mesuré sur TArC : 3 = ع (99 %), 7 = ح (95 %), 9 = ق (96 %), 5 = خ (96 %), 2 = ء (hamza). 4, 6 et 8 sont trop rares pour conclure. |
| `translitteration_arabizi_tarc.csv` | 11 500 mots arabizi avec leur écriture en lettres arabes, appris sur TArC (« 3andi » → عندي, « kifech » → كيفاش). |
| `variantes_arabizi_tarc.csv` | Pour chaque mot tunisien du lexique, toutes ses orthographes arabizi vues dans TArC. |
| `outils/normaliser.py` | Le petit module à brancher avant la recherche RAG (voir plus bas). |
| `tests/` | Les questions de test, le script de test et les résultats. |

## 4. Comment l'utiliser dans Dalila

```python
from normaliser import NormaliseurTunisien
n = NormaliseurTunisien()
r = n.analyser("chnowa lwra9 lazmin bech na5ou ma9sem sina3i?")
r["tunisien"]         # True : le message est en tunisien
r["concepts"]         # ['quoi', 'papiers', 'falloir', 'pour', 'prendre', 'terrain', 'industriel']
r["requete_pour_rag"] # la question + "papiers وثائق terrain قطعة أرض ..." : à envoyer à ChromaDB
r["en_arabe"]         # l'arabizi en lettres arabes, utile pour la voix
```

Le module ne garde que les formes attestées. `NormaliseurTunisien(inclure_a_valider=True)` ajoute les formes à valider.

## 5. Résultats des tests

32 questions dans `tests/questions_test.csv` : 6 vraies questions tunisiennes (2 visiteurs + 4 exemples du cahier des charges), 1 exemple du document d'équipe de Fida, 6 vraies questions en français, arabe standard et anglais (pour vérifier qu'elles ne sont **pas** prises pour du tunisien), et **19 questions tunisiennes que j'ai écrites moi-même** (marquées `ecrite_par_claude_a_relire`). Elles servent seulement au test et doivent être relues par un Tunisien.

La recherche est une recherche par mots-clés (BM25) dans les 156 réponses de l'AFI (réponses validées, fiches zones, formulaires, procédures). On regarde si la bonne réponse est dans les 5 premiers résultats.

| Mesure | Lexique attesté seulement | Avec les formes à valider |
|---|---|---|
| Langue bien reconnue (tunisien ou non) | 31 / 32 | 32 / 32 |
| Idées bien reconnues | 101 / 116 | 111 / 116 |
| Bonne réponse trouvée **sans** lexique | 16 / 30 | 16 / 30 |
| Bonne réponse trouvée **avec** lexique | **21 / 30** | **24 / 30** |

Sur les seules questions tunisiennes, le lexique fait passer la recherche de **12 à 17 sur 25** (20 avec les formes à valider). Exemple : « chnowa lwra9 lazmin bech na5ou ma9sem sina3i? » ne trouvait que des pages générales (contact, missions de l'AFI) ; avec le lexique, Dalila trouve la réponse « إجراءات الاقتناء » et les formulaires de demande d'acquisition d'un lot.

Deux leçons des tests :
- **N'enrichir que les messages tunisiens.** Enrichir une question déjà en français ou en arabe standard la rend moins précise (« أسعار المقسم؟ » trouvait la bonne réponse sans lexique, plus avec). Le champ `requete_pour_rag` applique déjà cette règle.
- **Les formes à valider aident** (+3 bonnes réponses). Faire valider les 175 formes par un Tunisien de l'équipe est le gain le plus rapide.

Ces tests sont petits et en partie écrits par moi. Le jury apportera ses propres questions le jour J.

## 6. Ce qui reste à faire (équipe)

1. Faire relire par un Tunisien de l'équipe la colonne `formes_a_valider_par_un_locuteur` du CSV et les 19 questions `ecrite_par_claude_a_relire`. Pour valider une forme, l'ajouter dans `outils/candidats.py` puis relancer le script, ou la noter dans le CSV.
2. Ajouter de vraies questions tunisiennes de l'équipe (au moins 30, comme prévu dans le plan de données), puis relancer `tests/tester_lexique.py`.
3. L'algérien et le libyen ne sont pas traités ici.

## 7. Relancer

```bash
python outils/construire_lexique.py --dalila <dossier dalila_final dézippé>
python tests/tester_lexique.py      --dalila <dossier dalila_final dézippé>
python outils/normaliser.py "n7eb terrain f Sfax"
```

Python 3 seul suffit, sans bibliothèque à installer.
