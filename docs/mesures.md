# Tableau de mesures de Dalila (livrable 3)

Mesures faites du 2026-11-27 au 2026-11-28, **sur processeur seul, 8 fils** (Intel Core i5-1135G7), comme sur le serveur
de l'AFI, qui n'a pas de carte graphique. Chaque chiffre vient d'un fichier de `eval/reports/` et peut être refait avec la
commande indiquée (depuis la racine du projet, avec `.venv\Scripts\python`).

## 1. Résumé : cibles du cahier des charges

| Exigence | Cible | Mesuré | Verdict |
|---|---|---|---|
| **BNF1** : chiffres exacts, tous tirés des données de l'AFI | 100 % | Le harnais vérifie chaque nombre et chaque zone ou lot cité avant l'envoi ; nombre de lots juste dans **10 réponses sur 16** au banc d'essai (voir § 2) | Vérification en place ; exactitude du modèle à améliorer |
| **BNF2** : temps de réponse à l'écrit | ≤ 35 s | Médiane **19,5 s**, 95 % des réponses en moins de **31,9 s**, **aucune** au-delà de 35 s (40 questions) | Atteint |
| **BNF3** : reconnaissance de la voix | ≤ 4 s | Médiane **3,0 s** (fr, en, de, tr, ar) ; **3,7 s** en tunisien sur de vrais extraits | Atteint, sauf phrases tunisiennes de plus de 6 à 8 s |
| **BF22** : démarche trouvée dans les 8 langues | 8 langues | **9 sur 9** (8 langues, tunisien écrit en lettres latines et en lettres arabes) | Atteint |
| Détection de la langue | 8 langues | **24 sur 24** sur le jeu des 8 langues ; **54 sur 57** sur de vraies questions | Atteint |

## 2. L'agent (réponses écrites)

Banc d'essai de 40 questions (35 jugées automatiquement), mêmes questions pour chaque modèle.
Commande : `python -m eval.agent_bench --modeles dalila-qwen3-4b,qwen3:4b-instruct,qwen3:1.7b` -> `agent_resume.json`.

| | **dalila-qwen3-4b** (ajusté, retenu) | qwen3:4b-instruct (de base) | qwen3:1.7b |
|---|---|---|---|
| Réponses justes | **22 / 35** | 23 / 35 | 4 / 35 |
| Nombre de lots exact (outil) | **10 / 16** | 11 / 16 | 1 / 16 |
| Nombre de lots juste dans la réponse | **10 / 16** | 11 / 16 | 0 / 16 |
| Bon passage trouvé (textes de l'AFI) | **9 / 15** | 8 / 15 | 0 / 15 |
| Réponse dans la langue de la question | **37 / 37** | 35 / 37 | 26 / 27 |
| Réponses de secours (repli) | 0 | 0 | 11 |
| Temps médian | **19,5 s** | 23,1 s | 11,1 s |
| 95 % des réponses en moins de | 31,9 s | 31,5 s | 78,9 s |
| Réponses au-delà de 35 s | **0** | 0 | 12 |

**Pourquoi le modèle ajusté a une bonne réponse de moins (22 contre 23).** L'écart d'une question sur 35 n'est pas
significatif : les deux modèles ne ratent pas les mêmes questions. Cinq questions changent de résultat :

| Question | Base | Ajusté | Ce qui s'est passé |
|---|---|---|---|
| « cest qoui AFI » | raté | **juste** | La base répond « hors sujet » ; l'ajusté cherche dans les textes de l'AFI. |
| « le pdg de l'afi » | raté | **juste** | Même chose. |
| « Kairouan lot supérieur a 5000 » | juste | raté | Erreur de l'ajusté : 5 000 lu comme un prix maximum au lieu d'une surface minimum. |
| « je veux terain subvention 65% » | juste | raté | Erreur de l'ajusté : 65 % lu comme un budget ; il liste des lots. |
| « nombre de promoteurs enregistrés » | juste | raté | Le test attendait un refus ; l'ajusté cherche, ne trouve rien et le dit. Réponse acceptable. |

Ce que l'ajustement améliore vraiment :

- **Il appelle les outils seul** : le harnais a dû rappeler au modèle de base d'appeler un outil **19 fois** sur
  40 questions, au modèle ajusté **0 fois**. C'est ce qui le rend plus rapide (19,5 s contre 23,1 s de médiane).
- **Il répond toujours dans la langue de la question** (37 sur 37, contre 35 sur 37).
- Il trouve un peu plus souvent le bon passage (9 sur 15, contre 8 sur 15).

Il n'est donc pas plus juste : il reste deux erreurs de lecture des nombres (une surface prise pour un prix, un
pourcentage pris pour un budget). Le second ajustement prévu ajoutera des exemples de ce type.

Le 1.7b est écarté : trop d'erreurs et de réponses trop lentes.

Test BF22 (une démarche, « la banque me demande un papier pour mon prêt », dans chaque langue) :
`python -m eval.bf22_langues` -> `bf22_langues.json`. Bon service trouvé **9 fois sur 9** (fr, en, ar, de, tr, tunisien en
lettres latines et arabes, algérien, libyen), en **28 s environ** chaque fois.

## 3. La voix

Commande : `python -m eval.voix_bench` -> `voix_resume.json` ; sur de vrais enregistrements :
`python -m eval.voix_bench --dossier <dossier d'extraits>`.

**Reconnaissance (voix -> texte)**, faster-whisper `small`, questions de 2 à 5 s lues par une voix de synthèse :

| Langue | Langue détectée | Temps | Mots justes |
|---|---|---|---|
| Français | oui | 3,0 s | 87 % |
| Anglais | oui | 3,0 s | 100 % |
| Allemand | oui | 3,0 s | 83 % |
| Turc | oui | 3,0 s | 67 % |
| Arabe | oui | 3,1 s | 86 % |
| **Ensemble** | **5 / 5** | **médiane 3,0 s, maximum 3,1 s** | **85 %** |

**Dialectes, sur de vrais extraits** (part de mots faux, puis de caractères faux ; plus bas = mieux) :

| | Whisper `small` seul | Réglage retenu (modèle tunisien pour l'arabe) |
|---|---|---|
| Tunisien (LinTO, 25 extraits) | 69 % / 28 % | **38 % / 19 %** (médiane 3,7 s) |
| Libyen (lahgtna, 20 extraits) | 33 % / 12 % | 46 % / 18 % |
| Algérien (télévision, 20 extraits) | 94 % / 54 % | 93 % / 53 % |

**Lecture (texte -> voix)**, Piper : une réponse est prête à être lue en **0,7 s** (fr, en, de, tr) et **1,0 s** (arabe).

## 4. Langue et recherche dans les textes

Détection de la langue : `python -m dalila.langue.detection --mesurer` -> `detection_langue.json`.

| Jeu de test | Justes |
|---|---|
| 8 langues (3 phrases chacune) | **24 / 24** |
| Vraies questions des visiteurs | **54 / 57** |
| Lexique tunisien | **30 / 32** |

Recherche des passages dans les textes de l'AFI (le bon passage parmi les 5 premiers) : `python -m eval.recherche_bench`
-> `recherche_regles.json` ; comparaison des modèles : `python -m eval.comparer_modeles` et `python -m eval.vitesse_cpu`.

| Jeu de test | Bon passage dans les 5 premiers | Temps médian |
|---|---|---|
| Vraies questions | 10 / 15 | 2,0 s |
| Questions en tunisien | 17 / 30 | 1,9 s |
| 8 langues | 14 / 16 | 1,9 s |

Modèle retenu : BGE-M3, sans reranker (le reranker n'améliore rien et ajoute 15 s sur processeur). Détail des
6 réglages comparés : `docs/decisions.md`, section « Modèle de recherche ».

## 5. Précautions de lecture

- Les jeux de test sont petits (15 à 57 questions) et surtout en français (49 vraies questions sur 57).
- La reconnaissance du français, de l'anglais, de l'allemand, du turc et de l'arabe a été mesurée sur des voix de
  synthèse : c'est optimiste. Les dialectes, eux, ont été mesurés sur de vrais enregistrements.
- Tous les temps sont pris sur un ordinateur portable à 8 fils ; le serveur de l'AFI (8 vCPU) devrait donner des
  temps proches.
