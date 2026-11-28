# Module apprentissage

Repère les questions mal comprises, fréquentes ou mal notées ; prépare synonymes, concepts et connaissances ; les contrôle (source vérifiable, plusieurs conversations distinctes, SHACL et OWL, jeu de test sans baisse) et les publie dans le graphe nommé `appris/<id>` ; journal et annulation.

| | |
|---|---|
| **Exigences** | BF12, BF18, BF19, BF21, BNF15, BNF16, BNF17, BNF18 |
| **Contrat** | Tables `agent_learning_candidates` et `agent_learning_journal` (déjà créées). Jamais un prix, une disponibilité ou une condition venus d'un visiteur ; questions anonymisées avant analyse. |
| **S'appuie sur** | semantique, connaissances (construire_abox) |
| **État** | Fait : la boucle d'apprentissage est **journal -> liste pour l'AFI -> exemples vérifiés -> ajustement mesuré** (voir ci-dessous) ; noms de lieux appris en direct. À faire : écran d'administration, synonymes vers le graphe, ajustement périodique automatisé. |

## Comment Dalila apprend

1. **Journal** : chaque tour est gardé anonymisé (`agent_turns` : question, outils, réponse du modèle, repli, avis).
2. **Liste pour l'AFI** (BF12, BF24) : `python -m dalila.apprentissage.besoins [--csv fichier]` : les questions qui
   ont fini en repli ou ont été notées « pas utile », les plus fréquentes d'abord. L'AFI y voit ce qui manque.
3. **Exemples vérifiés** : `python -m dalila.apprentissage.exporter` : les conversations réussies deviennent des
   exemples d'entraînement, seulement si les outils, rappelés avec les données du jour, justifient encore chaque nombre ;
   jamais une question du jeu de test, jamais une réponse notée « pas utile ».
4. **Ajustement mesuré** : `python -m ajustement.generer --enseignant --reel`, entraînement sur Kaggle, puis le même banc
   d'essai ; le nouveau modèle n'est adopté que s'il fait mieux (BNF17), l'ancien reste disponible (retour arrière).
5. **En direct, les synonymes** : `python -m dalila.apprentissage.synonymes_appris` : un mot des visiteurs vers une
   activité de l'ontologie (au moins 2 conversations, 80 % d'accord, contrôles, journal, `--annuler`) ; lu en direct par
   la recherche des activités, ajouté au graphe (graphe nommé `appris/<id>`, SHACL et OWL RL) à chaque construction.
6. **En direct, les noms de lieux** : `python -m dalila.apprentissage.lieux_appris` (au moins 2 conversations, contrôles,
   journal, `--annuler`).

Tests : `python -m tests.apprentissage.test_apprentissage` et `python -m tests.apprentissage.test_besoins_export`.

