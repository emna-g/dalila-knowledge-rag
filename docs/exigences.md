# Exigences du cahier des charges : où et où en est-on

Chaque besoin du cahier des charges (BF : fonctionnel, BNF : non fonctionnel), le module qui le porte et son état.
**À tenir à jour** à chaque étape : c'est la carte de ce qui reste à faire. État au 2026-11-27 (soir).
Légende : **Fait** (vérifié), **Partiel** (une partie existe ou n'est pas mesurée), **À faire**.

## Besoins fonctionnels

| Réf. | Besoin (résumé) | Priorité | Module | État |
|---|---|---|---|---|
| BF1 | Détecter la langue parmi les 8, distinguer tunisien, algérien, libyen, arabe standard | Obligatoire | `dalila/langue` | Fait (`dalila/langue/detection.py` : modèles CAMeL MADAR-26 et n-grammes ; 24/24 sur le jeu des 8 langues, « n7eb terrain f Sfax » -> tunisien ; rendue par l'API) |
| BF2 | Comprendre le tunisien, mêlé de français, sans orthographe fixe | Obligatoire | `dalila/langue`, `dalila/semantique` | Partiel (lexique attesté ; recherche 20/30 sur le jeu tunisien) |
| BF3 | Répondre dans la langue et l'écriture du visiteur | Obligatoire | `dalila/langue` | Fait (fr, en, ar, de, tr, dialectes en lettres arabes : rappel de langue du harnais ; langue juste 35/37 au banc d'essai) ; arabizi faible |
| BF4 | Fonctions existantes dans les 8 langues (terrain, proximité, qualification, procédure, étude) | Obligatoire | `dalila/traitement`, `dalila/harnais` | Fait : recherche de terrain, proximité, qualification du projet (outil `conseiller`), procédures (`demarche`), étude de projet guidée (10 questions puis PDF, `dalila/traitement/etude.py`) ; déclenchement vérifié en 8 langues pour BF22 |
| BF5 | Garder zones cliquables et boutons de choix après reformulation | Obligatoire | `dalila/communication`, `dalila/harnais` | Fait (balises écrites par le harnais à partir des résultats d'outils, `harnais/vues.py`) |
| BF6 | Dire quand l'information manque, orienter vers l'AFI | Obligatoire | `dalila/harnais` | Fait (repli avec le contact de l'AFI ; lieu inconnu jamais pris pour « aucune zone ») |
| BF7 | Poser une question à la voix dans les 8 langues | Obligatoire | `dalila/voix`, `frontend` | Fait côté service (`POST /carte/voix/transcrire` : langue détectée seule ; Whisper small pour fr, en, de, tr ; modèle tunisien whisper-tn-ct2 pour l'arabe et les dialectes) ; micro : interface |
| BF8 | Lire la réponse à voix haute | Obligatoire | `dalila/voix` | Fait (`POST /carte/voix/lire`, Piper : fr, en, de, tr, ar ; dialecte lu par la voix arabe EN LE SIGNALANT, en-tête `X-Dalila-Lecture` ; arabizi converti en lettres arabes avant lecture) |
| BF9 | Activer ou couper micro et lecture | Obligatoire | `frontend` | À faire |
| BF10 | Enchaîner plusieurs actions (agent à outils) | Souhaité | `dalila/harnais`, `dalila/traitement` | Fait (agent à outils : `dalila/harnais/agent.py`) |
| BF11 | Préparer une demande d'acquisition, sans dépôt sans confirmation | Souhaité | `dalila/traitement/demande.py`, `frontend/app/src/components/DemandeAcquisition.tsx` | Fait : formulaire prérempli (lot et prix relus dans la base, projet de l'étude guidée), PDF seulement après la case « J'ai vérifié » (sinon 400), fait en mémoire, ni déposé ni gardé ; ouvert depuis la fiche d'un lot ou depuis une réponse de Dalila sur l'achat (balise `[[DEMANDE]]`) ; fr, ar, en |
| BF12 | Lister pour l'AFI les questions en dialecte mal comprises | Souhaité | `dalila/apprentissage`, `dalila/communication/admin.py`, `frontend/app/src/admin` | Fait : écran « Questions mal traitées » de /admin/ (repli ou « pas utile », par fréquence et langue, commentaires, filtre par date, export CSV) ; aussi `python -m dalila.apprentissage.besoins` |
| BF13 | Conversation vocale continue | Souhaité | `dalila/voix`, `frontend` | À faire |
| BF14 | Lire les URL de la configuration, répondre avec le lien de la source | Obligatoire | `dalila/sources` | Partiel (corpus des sites officiels lu une fois ; lecture par configuration à faire) |
| BF15 | État de chaque URL (lecture, échec, relance), PDF compris | Souhaité | `dalila/sources`, `dalila/communication/admin.py`, `frontend/app/src/admin` | Fait : écran « Sources » de /admin/ (chaque URL de la configuration : à jour, en erreur avec le code, à relire, en retard, jamais lue, inactive ; PDF compris) |
| BF16 | Ontologie OWL/RDF, 9 familles, 8 langues | Obligatoire | `ontology/`, `dalila/connaissances` | Fait pour les familles (SHACL conforme, OWL RL sans erreur, une requête par famille) ; libellés de/tr/dz/ly à relire |
| BF17 | Comprendre par le sens, pas seulement par mots-clés | Obligatoire | `dalila/semantique`, `dalila/traitement/graphe.py` | Partiel (recherche par le sens : BGE-M3 choisi, voir decisions.md ; outil `relier_concepts` sur le graphe ; correspondance des activités par le sens à faire) |
| BF18 | Apprendre des questions mal comprises, fréquentes, mal notées | Obligatoire | `dalila/apprentissage` | Fait : synonymes appris des conversations (`synonymes_appris.py` : « 7out », « sardine » d'abord compris « Enseignement », bien compris après publication ; test), noms de lieux (`lieux_appris.py`), exemples vérifiés pour le prochain ajustement (`exporter.py`) |
| BF19 | Contrôler automatiquement puis publier ce qui est appris | Obligatoire | `dalila/apprentissage` | Fait : contrôles automatiques puis publication sans humain (mot anonyme et pas un nombre, concept existant, pas le libellé d'un autre, mène au bon concept, tests des outils) ; au graphe, graphe nommé `appris/<id>` contrôlé par SHACL et OWL RL à la construction (vérifié : conforme) |
| BF20 | Raisonner sur le graphe pour conseiller | Souhaité | `dalila/semantique` | Partiel (requête de test BF20 : pêche → APIA, port) |
| BF21 | Journal de l'apprentissage et annulation a posteriori | Obligatoire | `dalila/apprentissage`, `dalila/communication/admin.py`, `frontend/app/src/admin` | Fait : écran « Apprentissage » de /admin/ (noms de lieux et synonymes, contrôles, dates) avec un bouton « Annuler » confirmé ; le journal garde la date et l'auteur ; un ajout annulé n'est plus utilisé (testé) |
| BF22 | Guider vers le bon service par des questions à choix | Obligatoire | `dalila/harnais`, `dalila/traitement` | Fait (test d'acceptation dans les 8 langues : 9/9, tunisien en arabizi et en lettres arabes compris ; `eval/bf22_langues.py`) |
| BF23 | Conditions, pièces, frais, lieu de dépôt, lien de chacun des 8 services | Obligatoire | `dalila/traitement`, base de connaissances | Fait (outil `demarche` : les 8 services, réponses validées de l'AFI, lien, contact) |
| BF24 | Service non couvert : contact AFI, besoin enregistré | Obligatoire | `dalila/harnais` | Fait (repli avec contact ; question gardée dans `agent_needs` par l'API) |

### Besoins BF25 à BF40 (numérotation de l'équipe, pas celle du jury)

Le cahier des charges officiel s'arrête à BF24. Ces besoins viennent du document de l'équipe « Cahier des charges
Dalila » (fusion du cahier officiel, de DALILA.pptx et de afi.sql) ; ils détaillent ce que le cahier officiel demande
ailleurs : BF4 (qualification du projet, étude de projet), cas d'utilisation 6 et 7, annexe I.

| Réf. | Besoin (résumé) | Priorité | Module | État |
|---|---|---|---|---|
| BF25 | Lot ou regroupement de lots selon superficie, lieu, budget, calculé en base | Obligatoire | `dalila/traitement/lots.py` | Fait (outil `chercher_lots`, testé) |
| BF26 | Zone par proximité (port, gare, aéroport, autoroute) | Obligatoire | `dalila/traitement/zones.py` | Fait (`zones_proches`, `proche_de`) |
| BF27 | Comparer 2 à 4 zones : prix, surface disponible, accès, développement régional | Obligatoire | `dalila/traitement` | À faire |
| BF28 | État d'un lot : disponible, réservé, vendu, aux enchères | Obligatoire | `dalila/traitement` | Partiel (disponibles et mis aux enchères ; les autres états à exposer) |
| BF29 | Expliquer pourquoi un lot est recommandé | Obligatoire | `dalila/traitement`, `dalila/harnais` | À faire |
| BF30 | Activité autorisée dans la zone, incompatibilités avec les voisins (par secteur) | Souhaité | `dalila/traitement` | Partiel (cahiers des charges cherchés par `chercher_passages`) |
| BF31 | Qualifier le projet (région, emplois, investissement, superficie) et donner un guide sourcé | Obligatoire | `dalila/traitement` | Fait (outil `conseiller` : guide complet et sourcé, `dalila/traitement/projet.py` ; cahier officiel : BF4, cas d'utilisation 6) |
| BF32 | Étude de projet guidée : 10 questions, puis PDF | Souhaité | `dalila/traitement` | Fait (`dalila/traitement/etude.py` : 10 questions à boutons dans la langue du visiteur, guide du projet, PDF en fr, en, ar, de, tr ; `POST /carte/etude`, `GET /carte/etude/{id}.pdf` ; cahier officiel : BF4, cas d'utilisation 7) |
| BF33 | Expliquer les avantages : développement régional, aide déduite du prix, organisme | Obligatoire | `dalila/traitement` | Partiel (prix subventionné, groupe, organismes ; explication à rassembler) |
| BF34 | Conversation guidée par boutons pour une demande large | Obligatoire | `dalila/harnais` | Partiel (`[[CHOIX]]` pour les lieux et les services) |
| BF35 | Promoteur connecté : demandes, favoris, conversations | Souhaité | interface | Interface |
| BF36 | L'agent AFI gère connaissances, concepts, synonymes, avec retour arrière | Obligatoire | `dalila/administration` | Partiel (noms de lieux appris et annulables) |
| BF37 | L'agent AFI ajoute ou retire une URL et relance la lecture | Obligatoire | `dalila/sources` | Partiel (`config_sources.csv`, relecture hebdomadaire ; écran : interface) |
| BF38 | Besoins analysés : profil, intention, stade, sentiment, questions sans réponse | Souhaité | `dalila/apprentissage` | Partiel (questions sans réponse : `besoins.py`) |
| BF39 | L'administrateur choisit moteurs, voix, langues, droits, sans code | Obligatoire | `dalila/config.py` | Partiel (moteurs et voix par `.env` ; écran : interface) |
| BF40 | Avis utile / pas utile avec commentaire, alimente l'apprentissage | Obligatoire | `dalila/communication` | Fait côté service (avis et commentaire facultatif, flux F06 ; liste pour l'AFI) ; boutons : interface |

## Besoins non fonctionnels

| Réf. | Besoin (résumé) | Cible | Module | État |
|---|---|---|---|---|
| BNF1 | Tout chiffre vient des données de l'AFI | 100 % | `dalila/harnais` (ancrage), vues `v_pub_*` | Fait (vérification d'ancrage de chaque nombre et balise ; listes écrites par le harnais) |
| BNF2 | Temps de réponse à l'écrit | ≤ 35 s | `dalila/harnais`, `dalila/moteurs` | Fait (banc d'essai, processeur 8 fils : médiane 23 s, aucune réponse au-delà de 35 s) |
| BNF3 | Reconnaissance vocale | ≤ 4 s | `dalila/voix` | Fait (≈ 2,8 s en fr, en, de, tr ; ≈ 3,7 s en tunisien sur de vrais extraits ; plus de 4 s pour des phrases de plus de 6 à 8 s) |
| BNF4 | Panne d'une API : réponse en texte quand même | aucune erreur brute | `dalila/harnais` | Fait (moteur arrêté, délai, base injoignable : réponse en texte ; tests du harnais) |
| BNF5 | Français, anglais, arabe sans régression | jeu de test | `eval/` | Partiel (jeux de test en place) |
| BNF6 | Ordinateur, tablette, téléphone ; droite à gauche | 3 formats | `frontend` | À faire |
| BNF7 | Toute réponse vocale existe en texte | toutes | `dalila/voix`, `frontend` | Fait (la réponse est toujours du texte ; la voix en est la lecture) |
| BNF8 | Consentement micro, audio non conservé | démonstration | `frontend`, `dalila/voix` | Fait côté service (audio décodé en mémoire, jamais écrit ni gardé) ; consentement : interface |
| BNF9 | Clés hors du code, HTTPS, aucune donnée personnelle vers un service externe | aucune clé | tous | Fait pour l'existant (modèles locaux uniquement, `.env` hors git) |
| BNF10 | Moteurs interchangeables par configuration | sans code | `dalila/moteurs` | Fait (`DALILA_LLM`, `DALILA_MODELE`, `DALILA_STT` dans `.env`, sans code) |
| BNF11 | Service à part avec une API HTTP, démarrage documenté | — | `dalila/communication`, README | Fait (`dalila/communication/api.py`, démarrage dans le README) |
| BNF12 | Licence et coût de chaque modèle déclarés | liste complète | `docs/` | Fait (docs/decisions.md, « Modèles, licences et coûts ») |
| BNF13 | Mêmes zones et chiffres dans les 8 langues | 100 % | `dalila/harnais`, `eval/` | À faire |
| BNF14 | Seules les URL configurées ; page = donnée, jamais instruction | page piégée sans effet | `dalila/sources`, `dalila/harnais` | À faire |
| BNF15 | Chaque ajout daté, sourcé, contrôlé ; versions | retour arrière | `dalila/apprentissage` | Fait : chaque ajout garde ses conversations, sa date et ses contrôles ; graphes nommés `appris/<id>` ; graphe précédent gardé (`ontology/store.prev`) |
| BNF16 | Questions anonymisées avant apprentissage | aucun nom, téléphone, CIN, RNE | `dalila/harnais`, `dalila/apprentissage` | Fait (`anonymiser` : courriel, téléphone, CIN, RNE et matricule fiscal par leur format ; noms de personnes par un modèle de reconnaissance d'entités, Davlan/xlm-roberta-base-ner-hrl, AFL-3.0 ; les lieux connus sont gardés ; testé) |
| BNF17 | Gain d'apprentissage mesuré avant / après, par langue | hausse | `eval/` | Partiel : chaque ajustement est mesuré sur le même banc d'essai avant adoption ; mesure par langue limitée par le jeu de test (surtout français) |
| BNF18 | Jamais apprendre un prix, une disponibilité, une condition d'un visiteur ; plusieurs conversations | aucun ajout sans source | `dalila/apprentissage` | Fait : au moins 2 conversations distinctes et 80 % d'accord ; jamais un nombre ; seulement « ce mot désigne ce concept » ou « ce nom désigne ce lieu » |
| BNF19 | OWL 2, RDF, SPARQL 1.1, libellés avec langue, export Turtle | export sans erreur | `ontology/`, `dalila/connaissances` | Fait (export TriG/Turtle, SHACL, OWL RL, requêtes de test) |

| BNF20 | Proposer un conseiller AFI quand la question dépasse Dalila | contact proposé | `dalila/harnais` | Fait (repli avec le contact de l'AFI) |
| BNF21 | Charte graphique AFI et mascotte | couleurs, typographies | interface | Interface |

## Livrables

| Livrable | Où | État |
|---|---|---|
| Dépôt avec fichier d'installation, sans clé ni donnée personnelle | README.md | Partiel |
| Démonstration écrit et voix, 8 langues, arabizi | `frontend`, `dalila/` | À faire |
| Tableau de mesures (voix, temps, exactitude des chiffres) | `eval/reports/` | Fait (agent : `agent_resume.json` ; voix : `voix_resume.json` ; recherche) |
| Liste des API et modèles, licence et coût | `docs/` | Fait (docs/decisions.md ; API : README) |
| Note d'une page : limites et travail restant | `docs/limites.md` | Partiel |
