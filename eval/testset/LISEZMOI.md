# Jeu de test de Dalila : comment l'agrandir

Le jeu actuel (30 questions, `lexicon/tests/questions_test.csv`) est petit, et 19 de ses questions ont été écrites
par l'auteur du lexique. Pour une évaluation honnête, **les nouvelles questions doivent être écrites par d'autres
membres de l'équipe**, dans les 8 langues, sans regarder les passages avant d'écrire.

## Fichiers

| Fichier | Rôle |
|---|---|
| `MODELE_questions.csv` | Le modèle à copier : une ligne par question, colonnes expliquées ci-dessous. |
| `questions_claude_a_relire.csv` | 24 questions d'exemple **écrites par Claude** (3 par langue). Elles montrent le format. Elles ne comptent pas dans le score officiel tant qu'un membre ne les a pas relues (`statut_relecture = relue`). |

## Colonnes

| Colonne | Contenu |
|---|---|
| `id` | Identifiant unique (ex. `E-fr-01`). |
| `langue` | `fr`, `en`, `ar`, `de`, `tr`, `tn` (tunisien, lettres arabes ou arabizi), `dz` (algérien), `ly` (libyen). |
| `question` | La question telle qu'un investisseur l'écrirait, fautes comprises. |
| `ecrite_par` | `equipe:<prénom>` ou `claude`. |
| `statut_relecture` | `a_relire` ou `relue`. |
| `scenario` | `lots`, `zone_commodites`, `regles_zone`, `demarche`, `incitation`, `hors_sujet`. |
| `passages_attendus` | Comment reconnaître une bonne réponse dans les 5 passages : `ids:p000014,p000012` ou `regex:Sidi Achour|services`. Vide pour une question de chiffres. |
| `verite_sql` | Pour une question de chiffres : la requête SQL sur les vues `v_pub_*` qui donne la bonne valeur (ex. `SELECT COUNT(*) FROM v_pub_lots_disponibles l JOIN v_pub_zones z USING(zone_id) WHERE z.gouvernorat_fr='Sfax'`). |
| `reponse_attendue` | La valeur attendue (texte court), pour vérification à la main. |

## Lancer

```
python -m eval.run_eval --questions eval/testset/<fichier>.csv
```
Les résultats vont dans `eval/reports/`.
