# Décisions

Les choix en vigueur et leurs preuves (2026-11-26). Les décisions sur chaque donnée (prix, distance, lot…) sont dans
[db/corrections/DESACCORDS.md](../db/corrections/DESACCORDS.md).

## Architecture

| Décision | Preuve |
|---|---|
| **Base propre à Dalila (option b)** : MariaDB 11.8 avec une **copie** des tables de l'AFI (afi.sql), rafraîchie depuis la carte publique de l'AFI par `dalila.connaissances.rafraichir_copie_afi` ; Dalila ne touche pas à la base de l'AFI. | Rafraîchissement limité : la carte est protégée contre les robots (CAPTCHA le 2026-11-27 après ~200 requêtes). Le script s'arrête sans rien écrire ; pour un rafraîchissement régulier, accès ou export à demander à l'AFI. La base de connaissances de l'AFI n'est pas sur la carte : elle reste celle d'afi.sql. |
| **MariaDB 11.8 LTS, source unique.** `afi.sql` chargé tel quel ; nos tables à côté. | Les vues donnent 673 lots disponibles, comme la carte publique de l'AFI (672) plus un lot à confirmer. `dalila_ro` ne peut pas lire `lots` (donc ni `LOT_PROMOTEUR`) ni les tables AFI. |
| **Les données de l'AFI sont lues en direct, jamais copiées.** Les vues `v_pub_*` lisent zones, lots, distances, équipements et services ; les réponses validées de l'AFI sont relues à chaque chargement. | Un changement dans la base AFI (étape d'un lot, prix) se voit tout de suite dans les vues ; testé. |
| **Corrections avec garde-fou.** Chaque correction garde la valeur AFI d'origine ; si l'AFI la change, la correction devient « périmée » et la valeur de l'AFI s'affiche (`v_dalila_corrections_etat`). | Testé : prix modifié dans la base → correction périmée, nouvelle valeur affichée. |
| **Un chiffre n'est stocké qu'une fois** : comptes calculés par les vues ; ni prix, ni distance, ni compte dans le graphe ni dans les passages (fiches de zone sans chiffre). | Règle SHACL `PasDeChiffresMetier` : 0 violation. |
| **Seuls les lots cessibles** (`LOT_NATURE` = 1) sont proposés, comme sur la carte de l'AFI. | Les 7 autres lots « disponibles » de la base sont des équipements publics, absents de la carte. |
| **Passages et vecteurs dans MariaDB** (colonne `VECTOR`, `VEC_DISTANCE_COSINE`, recherche exacte). | 8 858 passages. |
| **Ontologie écrite à la main**, faits générés depuis la base ; **SHACL** et **OWL RL** à chaque construction ; **Oxigraph** embarqué, graphes nommés `core`, `abox`, `lexique`, `a-valider`, `appris/<id>`. | SHACL conforme ; OWL RL : 0 erreur ; 11 requêtes de test répondent. |
| **Anciens noms des zones** (« ENFIDHA 2 », « KASSERINE 2 »…) : `skos:hiddenLabel`, reconnus dans les questions, jamais affichés. | « Enfidha 2 » → zone ENNFIDHA II ; « Gaafour » → GAFOUR. |
| **8 langues** ; traductions non vérifiées isolées dans le graphe `a-valider`. | fr, en, ar, de, tr, aeb, arq, ayl ; de/tr/arq/ayl à valider. |
| **Recherche guidée par le graphe** : zone reconnue → seulement son cahier des charges ; régime de la zone → fiches AFI du bon régime ; démarche → réponses validées de l'AFI en tête ; langue de la question en premier. | |

## Données

| Décision | Preuve |
|---|---|
| **Les données actuelles de l'AFI l'emportent** sur l'ancienne carte publique (afi.e-industrie.gov.tn) relevée pour la fusion. | La carte actuelle (carte.afi.nat.tn) donne les valeurs de la base pour 250/250 champs de zones, 528/528 distances et équipements, 2 955/2 958 lots ; les 3 lots restants ont été changés par l'AFI depuis l'export et sont corrigés. Nos contrôles (GPS des zones, contours des lots, site de l'AFI) donnent tort à l'ancienne carte chaque fois qu'ils permettent de trancher. |
| **Corpus nettoyé une fois** (`preparer_corpus`) : copies de tables AFI retirées, 227 doublons retirés, OCR illisible « secondaire ». | 76 passages OCR marqués (lisibilité < 60 %), dont tout le cahier de la parcelle 15 de Ben Arous (2007). La note n'est pas appliquée à l'arabe (non fiable). |
| **Erreur prouvée dans la base de connaissances de l'AFI** corrigée par extrait (numéro de téléphone de la réponse 3). | Page contact du site AFI et réponse 26. |
| **Groupe 1 ou 2 de chaque zone de développement régional** ajouté (la base AFI dit seulement oui / non), visible seulement tant que l'AFI garde la zone en développement régional. | Carte de la FIPA (décret 2017-389), lue sur le PDF (couleurs) : 3 zones en groupe 1, 27 en groupe 2. |
| **Plans de lotissement** : liens publics lus en direct dans la table AFI `zone_documents` (`v_pub_plans`). | Les 45 plans de la table répondent sur carte.afi.nat.tn/storage (vérifié le 2026-11-27). |

## Fraîcheur des données (à mettre en œuvre après le choix du modèle et l'API)

Chaque couche de données vieillit différemment ; aucune ne doit être citée plus vieille qu'elle ne le dit.

| Couche | Aujourd'hui | Décision |
|---|---|---|
| **Base de l'AFI** (lots, disponibilité, prix, zones, équipements) | Lue au moment de la question par les vues `v_pub_*` : en production sur le serveur de l'AFI, toujours à jour. Sur la copie de Dalila : aussi fraîche que le dernier `rafraichir_copie_afi`. | Rafraîchir la copie chaque jour tant que Dalila n'est pas sur le serveur de l'AFI. |
| **Corrections de Dalila** | Chaque correction garde la valeur de l'AFI qu'elle corrige ; si l'AFI change cette valeur, `v_dalila_corrections_etat` la marque périmée et la valeur de l'AFI s'applique. | Gardé tel quel : une correction ne masque jamais un changement de l'AFI. Les corrections périmées vont dans la liste à relire. |
| **Réponses validées de l'AFI** | Relues à chaque chargement ; vecteurs recalculés seulement si le texte change. | Gardé tel quel. |
| **Fichiers de référence** (`db/reference/*.csv` : prix du site, derniers prix publiés, groupes FIPA, régions, services) | Relevés une fois, sourcés, jamais revérifiés. Seul garde-fou : `prix_en_conflit` quand le site et la base diffèrent. | Chaque ligne reçoit sa date de consultation et l'empreinte de la page source ; revérification par le module sources ; une ligne dont la source a changé ou disparu passe en « à relire ». |
| **Textes officiels** (TIA, FIPA, APII, APIA, SICAD, lois, cahiers des charges) | Relevés une fois et vectorisés ; l'âge du texte n'est pas dit au visiteur. | Module sources : relecture au moins chaque semaine, empreinte de contenu, seuls les passages changés sont revectorisés ; un texte changé n'écrase pas une version validée sans relecture ; la réponse cite la date de consultation (« site de la FIPA, consulté le … »). En cas d'échec de lecture, la dernière version reste utilisée et l'échec est journalisé (`agent_source_status`). |
| **Graphe de connaissances** | Dérivé de la base et des règles sourcées ; reconstruit à la main (`construire_abox`). | Reconstruit automatiquement après chaque rafraîchissement, puis tests des outils en barrière : si un test échoue, l'ancienne version reste en service. |
| **carte.afi.nat.tn** | Protégée par CAPTCHA. | Pas de relecture automatique ; le CAPTCHA n'est jamais contourné. Seules la base de l'AFI et les pages publiques de son site sont relues. |

Alertes pour l'administration : corrections périmées, lignes de référence plus vieilles que leur délai de revérification,
pages disparues ou changées, échecs de lecture répétés.

## Orientations de l'équipe (à mettre en œuvre)

| Décision | Ce que le code fait aujourd'hui | À faire |
|---|---|---|
| **RAG agentique avec des modèles locaux uniquement** (Ollama ; aucun service d'IA externe, aucune clé) : le modèle choisit lui-même ses sources (passages par le sens, graphe, chiffres des vues) par appels d'outils. Le serveur de l'AFI n'a pas de carte graphique (8 vCPU, 16 Go) : modèle assez petit pour répondre en 35 s au plus (BNF2). | `dalila/harnais/pipeline_fixe.py` enchaîne toujours les mêmes étapes (graphe → chiffres → passages). | Exposer `chercher_passages`, `interroger_graphe` et les fonctions de `outils.py` comme outils de l'agent ; `dalila.py` disparaît. |
| **Pile propre à l'équipe, sans Laravel** : aucun code de l'application existante n'est fourni et l'équipe ne connaît pas Laravel. Service Python avec une API HTTP, interface libre. Le contrat `POST /carte/chatbot` (message, history, lang, contexte → message avec `[[ZONE]]`, `[[LOT]]`, `[[CHOIX]]`, `[[PDF]]`, log_id, source, action) est gardé pour que l'AFI puisse brancher le service plus tard (BNF11). | Pas d'API ni d'interface. | API HTTP (FastAPI) au contrat de `/carte/chatbot` ; interface choisie par l'équipe. |
| **Dalila = un harnais d'agent** : boucle d'outils typés et bornés, garde-fous en entrée et en sortie, couches de sécurité, repli sans erreur brute. | — | Voir « Le harnais de l'agent » ci-dessous. |
| **Pas de règles écrites à la main pour les langues** (pas d'expressions régulières ni de listes par langue). | `recherche.langue_de` (compte des lettres arabes), listes de mots vides (`comprendre.py`, `recherche.py`), normaliseur du lexique (`dalila/langue/lexique/`). | Laisser le modèle détecter la langue et reformuler la question ; un modèle de recherche multilingue (ajusté si besoin) remplace le lexique. |

## Ajustement des modèles

Agent : voir « Modèle de l'agent » (ajustement de secours en cours). Voix : ajuster Whisper `small` sur de la parole
tunisienne, algérienne et libyenne (voir « Voix »). Recherche :

Le modèle de recherche (BGE-M3) sera ajusté sur nos propres paires, puis remesuré sur le jeu de vraies questions,
**jamais utilisé pour l'entraînement**. Paires disponibles sans rien inventer :

| Tâche | Paires (entrée → cible) | Pourquoi |
|---|---|---|
| Relier un projet à la nomenclature (`conseiller`) | description d'un projet, dans les 8 langues et en arabizi → activité de la nomenclature de l'APII (501 libellés) | Aujourd'hui, la bonne activité est dans les 5 premières (12 cas sur 12) mais pas toujours première ; les libellés courts se distinguent mal. |
| Trouver la réponse de l'AFI (`chercher_passages`, `demarche`) | question de visiteur → réponse validée de l'AFI (85) ou passage qui y répond | Rappel@5 de 12/15 sur les vraies questions ; le tunisien reste le point faible (22/30). |

Les paraphrases dans les 8 langues sont produites par le modèle local à partir des libellés et des réponses de l'AFI,
puis vérifiées automatiquement (retrouvent-elles leur cible ?) ; les corpus tunisiens (TArC, TUNIZI, TSAC) apportent
l'écriture réelle (licences : démonstration seulement pour TArC).

## Le harnais de l'agent (en partie construit : `dalila/harnais/`)

Le cahier des charges n'emploie pas le mot « harnais », mais il exige presque toutes ses couches. Chaque couche est
testée par un jeu de questions dédié (dont des attaques), à chaque changement.

| Couche | Ce qu'elle fait | Exigé par |
|---|---|---|
| **Entrée** | Message de 500 caractères au plus, historique de 20 messages au plus ; données personnelles (téléphone, CIN, RNE, noms) masquées avant le modèle et avant tout journal. | F01, F10, BNF9, BNF16 |
| **Injection d'instructions** | Une question, une page web ou un passage ne peut jamais changer les consignes : les textes lus sont passés au modèle comme des données balisées, jamais comme des instructions ; seules les URL configurées sont lues. | VI.4, BNF14 |
| **Compréhension** | Le modèle local détecte la langue et l'écriture (8 langues, arabizi, mélange avec le français) et ramène la question à une forme comprise ; aucune règle écrite à la main. | BF1, BF2, BF3 |
| **Outils** | Liste fermée d'outils typés (schémas d'entrée et de sortie), lecture seule par le compte `dalila_ro` ; nombre d'étapes et temps bornés (35 s au total). Les questions larges reçoivent une question à choix (`[[CHOIX]]`). | BF4, BF10, BF22, BNF2 |
| **Actions** | Une action réelle (demande d'acquisition) est seulement préparée : brouillon prérempli, jamais déposé sans la confirmation du promoteur. | BF11 |
| **Ancrage de la réponse** | Avant l'envoi, chaque chiffre (prix, surface, nombre, distance, frais) doit se trouver dans les résultats des outils, chaque balise `[[ZONE]]`, `[[LOT]]`, `[[PDF]]` doit viser un identifiant rendu par un outil, chaque texte cité garde sa source ; sinon la réponse est refaite, ou remplacée par une réponse construite directement à partir des faits. | BNF1, BF5, BF23, BNF13 |
| **Règles métier** | Information absente : le dire et donner le contact de l'AFI ; service non couvert : contact AFI et besoin enregistré ; aucun montant de subvention calculé ; hors sujet : refus poli. | BF6, BF24, limites.md |
| **Repli** | Moteur ou voix en panne : réponse en texte depuis la base de connaissances ou les faits, jamais de message d'erreur brut. | BNF4, BNF7 |
| **Apprentissage sûr** | Un ajout exige plusieurs conversations distinctes, une source vérifiable, un graphe cohérent (SHACL, OWL) et aucune baisse sur le jeu de test ; jamais un prix, une disponibilité ou une condition venus d'un visiteur ; journal, annulation, versions. | BF18, BF19, BF21, BNF15, BNF17, BNF18 |
| **Journal et mesures** | Chaque tour (anonymisé) garde la langue, les outils appelés, les verdicts des garde-fous et le temps ; base du tableau de mesures des livrables. | Livrables, BF12 |

## Modèle de l'agent (mesuré sur processeur, 8 fils, comme le serveur de l'AFI)

Priorité : un modèle qui tient dans les contraintes du cahier des charges (modèle local, processeur seul, 16 Go,
réponse en 35 s). Le modèle retenu est **Qwen3-4B-Instruct-2507** (`qwen3:4b-instruct`). Un seul modèle choisit les
outils et écrit la réponse ; BGE-M3 reste le modèle de recherche. Le harnais compense ce qu'un petit modèle sur
processeur fait lentement ou mal ; un modèle plus grand ne sera proposé que si ces corrections ne suffisent pas, avec
les mesures à l'appui.

Jeu : 40 vraies questions (`eval/agent_bench.py`, rapports dans `eval/reports/`).

| Version | Réussies | Nombre de lots exact | Passage trouvé | Replis | Médiane | Au-delà de 35 s |
|---|---|---|---|---|---|---|
| Qwen3-1.7B | 4/35 | 1/16 | 0/15 | 11 | 11 s | 12 |
| Qwen3-4B (variante « thinking ») | dépasse 90 s à chaque question : écarté | | | | | |
| Qwen3-4B-Instruct, premier harnais | 9/35 | 4/16 | 5/15 | 14 | 54 s | 23 |
| Qwen3-4B-Instruct, harnais corrigé | 15/35 | 7/16 | 6/15 | 3 | 22 s | 2 |
| Qwen3-4B-Instruct, outils corrigés (*) | 23/35 | 11/16 | 8/15 | 1 | 21 s | 1 |
| **Qwen3-4B-Instruct, version livrée** (**) | **23/35** | **11/16** | **8/15** | **0** | **23 s** | **0** |

(*) Corrections d'outils : `relier_concepts` caché au modèle (il l'appelait sans enchaîner) ; `chercher_passages`
accepte un nom de zone ; `lister_zones` rend le nombre exact de lots ; choix explicite `hors_sujet`, outil obligatoire
à la première étape pour toutes les questions ; temps de lecture estimé sur la taille réelle des résultats. La notation
accepte désormais le nombre exact de lots rendu par `lister_zones` ou `fiche_zone` (avant : `chercher_lots` seul) ;
sans ce changement, 4 réponses justes (R07, R38, R39, R51) restaient comptées fausses.

(**) En plus : rappel de la langue du visiteur avant la réponse (langue juste 35/37, contre des réponses en français
pour l'allemand, le turc, l'arabe et les dialectes) ; lieu réécrit par le modèle recherché dans le message du visiteur ;
réponse qui boucle rejetée ; chiffre collé à des lettres lu comme une lettre (arabizi). Délai le plus long : 31,5 s.
Un essai de consigne « réponds en arabizi » a fait boucler le modèle même en français (18/35, 11 replis) : retiré,
la mesure l'a montré avant toute livraison.

Ce qui a coûté le temps (mesuré pas à pas) : le modèle **écrit** 4 à 6 jetons par seconde ; une réponse de 200 à 340
jetons prenait 50 à 120 s. La lecture n'est pas le problème une fois les consignes en cache (≈ 4 s par étape).
Corrections du harnais, sans changer de modèle :

| Correction | Effet |
|---|---|
| Les listes (lots, zones), balises, documents et sources sont écrits par le harnais à partir des résultats d'outils (`harnais/vues.py`) ; le modèle écrit 1 à 3 phrases. | Une centaine de jetons écrits en moins ; listes exactes par construction. |
| Borne d'écriture tirée du temps restant (≈ 4 jetons/s), réponse coupée à la dernière phrase complète. | La réponse finit avant 35 s au lieu d'être remplacée par le repli. |
| Vue courte de chaque résultat d'outil (2 000 caractères au plus au lieu de 6 000). | Moins de lecture à chaque étape. |
| Outil obligatoire à la première étape : si le modèle commence à écrire sans données, il est arrêté (≈ 1 s) et invité à appeler un outil, une fois. | Fin des réponses écrites « de mémoire » ; le hors-sujet reste refusé sans outil. |
| `resoudre_lieu` caché au modèle : `chercher_lots`, `lister_zones` et `fiche_zone` prennent le nom du lieu tel qu'écrit. | Une étape de moins ; fin des arrêts après la seule résolution du lieu. |
| Préchauffage avec les vraies consignes et les outils. | La première question ne paie plus 40 à 60 s de lecture. |
| Rappel de langue, ajouté juste avant la réponse et non gardé dans l'historique ; il cite le message du visiteur et la langue de l'interface. | Réponses dans la langue du visiteur (les résultats d'outils, en français, l'entraînaient vers le français). |
| Lieu inconnu (« Qassrin » pour « القصرين », « port » mis comme lieu) : recherché dans le message du visiteur, sinon le filtre de lieu est retiré. | Plus jamais « aucune zone » à tort (Kasserine : 29 lots). |
| Réponse qui répète la même suite de mots : rejetée, le modèle est relancé une fois, sinon repli. | Le tunisien en lettres arabes faisait boucler le modèle ; le visiteur ne voit jamais ce texte. |

Reste à corriger, propre au modèle : des questions sur l'AFI prises pour hors sujet (R11, R29), un lieu réécrit au
lieu d'être recopié (« Grand Tunis » → « tunis », R15), le mauvais outil pour un cahier des charges (R17) ; et 8/15
passages trouvés. Sur les 7 manqués, 4 viennent de l'agent (pas de recherche, ou question mal reformulée) : avec
les mots du visiteur, BGE-M3 trouve le passage attendu (rang 1 ou 2 pour R11, R17, R46 ; rang 7 pour R48). Seuls R29,
R42 et R47 (tunisien, question vague) sont des manques de la recherche elle-même.

**Ajustement du modèle (solution de secours, en cours)** : QLoRA de Qwen3-4B-Instruct sur Kaggle (jeu privé), 816
conversations en 9 variantes de langue (`ajustement/generer.py`) : appels d'outils vérifiés sur la base, réponses
ancrées ; le jeu de test n'y entre jamais. Même taille, même vitesse sur processeur (GGUF q4). Adopté seulement s'il
fait mieux que 23/35 au même banc d'essai, langue comprise. Un modèle plus grand ne serait proposé qu'ensuite, mesures
à l'appui.

## Voix (mesurée sur processeur, 8 fils)

| Rôle | Choix | Licence | Pourquoi |
|---|---|---|---|
| Voix vers texte, arabe et dialectes | **whisper-small-tunisian-derja-ct2** (« whisper-tn-ct2 » du cahier des charges, int8) | Apache 2.0 | Sur 25 vrais extraits tunisiens (LinTO, jeu de test, jamais vus à l'entraînement), sans langue donnée : 38 % de mots faux et 19 % de caractères faux, contre 69 % et 28 % pour Whisper `small` ; garde le français mêlé au tunisien ; 3,7 s de médiane (au-delà de 4 s seulement pour des phrases de 9 à 15 s). Seul, il prend l'allemand et le turc pour de l'arabe : il ne sert que quand Whisper `small` entend de l'arabe (probabilité ≥ 0,15). |
| Voix vers texte, fr, en, de, tr, et détection de la langue | **faster-whisper `small`** (int8) | MIT (modèle Whisper : MIT) | 3,0 s de médiane pour une question de 2 à 5 s (cible BNF3 : 4 s) ; langue détectée 5/5 ; exactitude 0,85 à 0,88 sur les mots. `large-v3-turbo` est plus exact (0,87) mais prend 16 s : écarté sur processeur. |
| Texte vers voix | **Piper** (voix fr, en, de, tr, ar) | MIT (moteur) ; voix : voir « Modèles, licences et coûts » | 0,7 à 0,9 s pour une réponse ; seul moteur local rapide qui couvre ces 5 langues. Kokoro (sans arabe, allemand, turc), XTTS-v2 et MMS-TTS (licences non commerciales, lents sur processeur) écartés. |

En français, anglais, allemand et turc seulement, les noms des gouvernorats de la base sont donnés à Whisper comme mots
favorisés (pas en arabe ni en dialecte : sur du tunisien mal compris, ils devenaient des suggestions, « عسلامة كيفاش
تنجم تعاوني » reconnu « lot Sfax Sidi Bouzid ») : « Janduba », « S-Fax », « Biz ertede »
deviennent Jendouba, Sfax, Bizerte (exactitude 0,78 -> 0,88, sans coût de temps mesurable). L'outil de lieu tolère
aussi les fautes restantes. Mesure faite avec des voix de synthèse (optimiste) : `eval/voix_bench.py --dossier` mesure
de vrais enregistrements dès qu'il y en a.

Dialectes maghrébins, mesurés sur de vrais extraits sans langue donnée (mots faux / caractères faux) :

| | Whisper `small` seul | Partage retenu (tunisien pour l'arabe) |
|---|---|---|
| Tunisien (LinTO, 25 extraits) | 69 % / 28 % | **38 % / 19 %** |
| Libyen (lahgtna, 20 extraits lus) | **33 % / 12 %** | 46 % / 18 % (en partie l'orthographe tunisienne : « باش تطور ») |
| Algérien (Casablanca, 20 extraits de télévision) | 94 % / 54 % | 93 % / 53 % |

Le partage est gardé : il divise par deux les erreurs en tunisien, la langue de la plupart des visiteurs de l'AFI ; la
parole seule ne permet pas de séparer libyen et tunisien avant transcription. L'algérien spontané échoue avec les deux
modèles : un ajustement sur CAFE (35 h, algérien mêlé de français, ouvert) serait nécessaire. Langue détectée seule, jamais choisie par le visiteur, limitée à fr, en,
ar, de, tr : laissé libre, Whisper prenait le tunisien pour du polonais. Synthèse en tunisien : TunArTTS (Elyadata,
Apache 2.0) demande un texte entièrement vocalisé ; à évaluer après la livraison. Autres modèles possibles : [FarukSTT](https://huggingface.co/medyas/FarukSTT) (Whisper large-v3
ajusté sur le tunisien, WER annoncé 32 % contre plus de 50 % pour la base ; trop lent sur processeur tel quel) et
[whisper-large-v3-arabic-dialectal-v2](https://huggingface.co/oddadmix/whisper-large-v3-arabic-dialectal-v2) (libyen et
algérien, chiffres sur très peu d'exemples). Un ajustement de Whisper `small` sur les jeux tunisiens ouverts (LinTO,
CC BY 4.0) garderait la vitesse.

## Modèle de recherche

**Choix : BGE-M3 (BAAI/bge-m3), sans reranker.** Mesuré le 2026-11-27 sur les 8 858 passages, mêmes questions, même
graphe (`python -m eval.comparer_modeles`, `python -m eval.vitesse_cpu`) :

| Réglage | Vraies questions (15) | Tunisien (30) | 8 langues (16) | Question encodée sur processeur (8 fils) |
|---|---|---|---|---|
| e5-small (ancien défaut) | 11/15, MRR 0,48 | 20/30, MRR 0,52 | 14/16, MRR 0,80 | 10 ms |
| **BGE-M3** | **12/15, MRR 0,70** | 22/30, MRR 0,60 | **16/16, MRR 0,93** | 77 ms |
| Qwen3-Embedding-0.6B | 11/15, MRR 0,61 | **22/30, MRR 0,65** | 16/16, MRR 0,87 | 532 ms |
| + reranker bge-reranker-v2-m3 | moins bon avec chaque modèle | | | 15 s pour 20 passages |

- Rappel@5 : la bonne réponse est dans les 5 premiers passages ; MRR : 1 si elle est première.
- BGE-M3 gagne sur le jeu principal (vraies questions de visiteurs) et sur les 8 langues, et reste rapide sur le
  processeur du serveur de l'AFI. Qwen3 fait un peu mieux sur le tunisien : à reprendre avec l'ajustement du modèle.
- Le reranker baisse les résultats et coûterait 15 s par question sans carte graphique : désactivé.
- Recherche exacte dans MariaDB : environ 1,7 s par question pour BGE-M3 (0,3 s pour Qwen3, même taille de vecteur :
  effet de stockage). Un index de vecteurs le ramènera à quelques millisecondes ; même sans, la réponse reste loin du
  budget de 35 s.

## Reporté

- SICAD et APIA : seulement les extraits de la base AFI (le module sources lira les URL configurées) ; INS et ministères : cités seulement, comme le prévoit le cahier des charges (voir limites.md).
- Jeu de test de l'équipe à écrire (`eval/testset/MODELE_questions.csv`) : les 24 questions d'exemple, écrites par Claude, sont faciles et ne comptent pas dans le score officiel.

## Modèles, licences et coûts (BNF12)

Tous les modèles tournent en local, sans clé ni service payant : coût nul à l'usage (processeur du serveur). Le service
n'appelle aucune API externe.

| Rôle | Modèle | Licence | Taille |
|---|---|---|---|
| Agent (outils et réponse) | Qwen3-4B-Instruct-2507 (`qwen3:4b-instruct`, Ollama) | Apache 2.0 | 2,5 Go (q4) |
| Recherche par le sens | BAAI/bge-m3 | MIT | 2,2 Go |
| Voix vers texte | Whisper `small` (faster-whisper, CTranslate2 int8) | MIT | 0,5 Go |
| Voix vers texte, tunisien | TheBiggyBang/whisper-small-tunisian-derja-ct2 (int8) | Apache 2.0 | 0,25 Go |
| Texte vers voix (moteur) | Piper | MIT | — |
| Voix française | fr_FR-siwis-medium | CC BY 4.0 (citer le jeu SIWIS) | 63 Mo |
| Voix anglaise | en_US-ljspeech-medium | domaine public | 63 Mo |
| Voix allemande | de_DE-thorsten-medium | CC0 | 63 Mo |
| Voix turque | tr_TR-dfki-medium | CC BY-NC-SA 4.0 | 63 Mo |
| Voix arabe | ar_JO-kareem-medium | non indiquée par son auteur | 63 Mo |
| Graphe | Oxigraph | MIT / Apache 2.0 | — |
| Base | MariaDB 11.8 | GPL v2 | — |

Les voix viennent de la liste officielle de Piper (rhasspy/piper-voices) ; ce sont les seules voix Piper en turc
et en arabe. La voix anglaise `ljspeech` (domaine public) remplace `lessac`.

