# Ce qui manque, et ce que Dalila doit dire

Ce qui est **absent de toutes nos sources** (les erreurs, elles, sont corrigées : voir `db/corrections/DESACCORDS.md`).
Vérifié le 2026-11-27 sur `afi.sql`, la carte publique actuelle de l'AFI (zones, lots, documents, indicateurs), les sites
officiels collectés et le corpus. Quand une information manque, Dalila le dit et renvoie vers l'AFI, au lieu de deviner.

## 1. Données de l'AFI

Ce qui manquait a été comblé avec des sources de l'AFI, chaque valeur ajoutée étant montrée à part, avec sa source :

| Manque | Comblé par | Reste sans source |
|---|---|---|
| **Prix** (prix 0 ou impossible dans la base) | Dernier prix publié par l'AFI, sur son ancienne carte (25/11/2026), « à confirmer » : Gabès I, II et III 50 DT/m², Sousse II 100, Bir El Kassaa 2 100 (champ `prix_m2_dernier_publie_dt`). | Sousse I et Hstaftimi : aucun prix dans aucune source (ni base, ni cartes, ni site) → contact de la direction commerciale (+216 71 124 242). |
| **Prix subventionné** (nouveau) | Page des incitations du site de l'AFI : prix au m² après la prime d'infrastructure (65 % groupe 1, 85 % groupe 2), 28 zones de développement régional (`prix_m2_subventionne_dt`). | — |
| **Prix en conflit** | El Kef Extension : 32 DT/m² dans la base et sur la carte actuelle, 118 sur l'ancienne carte et sur la page des incitations du site de l'AFI. Dalila donne 32, signale 118 (`prix_en_conflit`) et conseille de confirmer. | — |
| **Surface aménagée** | Bir El Kassaa 2 : 48,1 ha, surface couverte par les contours de ses lots (table AFI `lots_kml`) ; méthode vérifiée : elle retrouve la surface aménagée de l'AFI sur les zones qui en ont une (ex. Choutrana 41,7 / 41,3 ha). | — |
| **Surface totale** | — | Bir El Kassaa 2, Kasserine Extention, Bouficha 2 : la surface totale (voirie et espaces verts compris) ne se déduit pas des lots (rapport à la surface aménagée de 1,3 à 2,9 selon les zones) → « surface totale non publiée », avec la surface aménagée. |
| **Groupe 1 ou 2** | Carte de la FIPA (décret 2017-389), confirmée par la page des incitations de l'AFI : 3 zones en groupe 1, 27 en groupe 2. | — |
| **Plans de lotissement** | Les 45 plans de la table AFI `zone_documents`, publiés sur la carte (30 zones visibles), vue `v_pub_plans`. | 20 zones visibles sans plan dans la base de l'AFI. |
| **Enchères** | Procédure complète (réponses AFI 24 et 25). | Dates et mise à prix : vides dans la base et sur la carte → renvoi vers l'AFI. |
| **Équipements non renseignés** | — | Valeur 0 dans la base et sur la carte (34 zones pour le gaz, El Hancha pour tout) ; gazoducs nommés par une route (9 zones) → « information non disponible ». OpenStreetMap essayé le 2026-11-27 (237 tronçons de gazoduc en Tunisie) : il ne retrouve les distances de l'AFI que pour 3 zones sur 40 (écart médian 51 km), réseau incomplet : non utilisé. |
| **Lot à confirmer** | — | Lot 7204 (Sbikha 2) : disponible dans `afi.sql`, absent de la carte actuelle → « à confirmer auprès de l'AFI ». |

Remarque : la surface aménagée de l'AFI correspond bien à la surface des lots (contours) ; la somme brute des surfaces de
lots la dépasse parce que certains lots découpés figurent aussi sous leur numéro d'origine.

## 2. Services de l'AFI (BF23)

Vérifié le 2026-11-27 sur les réponses validées de l'AFI (12 à 25) et ses pages « Nos services » (fr, en, ar) : les 8
services ont leurs conditions ou étapes, leurs pièces et le lien de la source. Ce que l'AFI **ne publie pas** (détail
par service : `db/reference/services_afi.csv`) :

| Manque | Services | Ce que Dalila dit |
|---|---|---|
| Montant des frais de rédaction du contrat et de délimitation topographique | Acquisition d'un lot | « Montant non publié par l'AFI » (le cahier des charges interdit toute estimation de frais). |
| Frais de l'AFI | Autorisation de vente (leasing) | Seuls les frais du GMG sont cités : le dire. |
| Montant de la garantie, dates des ventes | Enchères | Fixés dans le cahier des charges de chaque vente : renvoyer vers l'AFI. |
| Lieu de dépôt (comblé) | Les 6 services administratifs | Champ `lieu_depot` de l'outil `demarche` : « demande écrite adressée au PDG de l'AFI » (réponses 18 à 23) et accueil au siège (9 et 13 rue Chott Mariem, Montplaisir, Tunis) et dans les délégations régionales (réponse 26). |

Frais publiés (cités tels quels) : attestation de situation foncière, d'insertion d'hypothèque et de mainlevée : 50 DT ;
acte de précision ou contrat final : 150 DT ; copie conforme : 15 DT par copie.

## 3. Cahiers des charges

- **Aucun cahier pour 14 zones de la carte** : Gabès I, II et III (159 lots disponibles), Om Laatham Sidi Bouzid (76),
  Kasserine Extention (24), Bouarada II (21), Oueslatia (17), Hajeb Laayoun (13), Gaafour (12), Bouficha 2 (2),
  Makther (1) ; et sans lot disponible : Jendouba, Sousse II, Tabarka 2, Bir El Kassaa 2, El Agba.
  Dalila dit que les règles d'activité de la zone ne sont pas disponibles et renvoie vers l'AFI.
  Vérifié le 2026-11-27 : la table AFI `zone_documents` cite un vrai cahier pour **Om Laatham** (`CC-OM-Laadham-2020.pdf`),
  mais ce fichier n'est publié ni sur la carte ni sur le site de l'AFI. Des 61 cahiers de cette table, nous avons tous
  ceux des zones visibles par le site afi.nat.tn, sauf celui d'Om Laatham (et celui de Bennane, zone masquée par l'AFI).
  À demander à l'AFI. Vérifié une seconde fois le 2026-11-27 : la page « CC.ZI.Oum-Laadham.Sidi Bouzid » du site de l'AFI
  renvoie bien au PDF de Sidi Ali Hattab ; le vrai fichier n'est publié nulle part.
- **Erreurs du site de l'AFI** (corrigées dans `db/reference/cahiers.csv`, colonne `remarque`) : la page d'Om Laatham
  propose le PDF de Sidi Ali Hattab ; « Sbikha 02 » propose celui de Soliman ; « Mghira 03 » celui de Zriba 2 et 3.
  Pour Kalaa Kebira, Kairouan II, Mghira 1 et Souassi, la page parle d'un projet ou d'une étude d'aménagement.
- **OCR** : 4 695 passages de cahiers sont lisibles ; 78 sont marqués « secondaire » (en-têtes, sommaires, pages de
  signatures, et tout le cahier de la parcelle 15 de Ben Arous, 2007, illisible). Un chiffre lu par OCR doit être cité
  avec le lien du PDF officiel (`texte_ocr = 1`).

## 4. Sources officielles

| Source (cahier des charges de Dalila) | Dans le corpus | Manque |
|---|---|---|
| AFI | Site (pages et PDF), 61 cahiers des charges, base de connaissances (85 réponses validées, lues en direct) | — |
| FIPA (investintunisia.tn) | 418 pages et PDF | — |
| APII (tunisieindustrie.nat.tn) | 246 pages, nomenclature des activités | — |
| TIA (tia.gov.tn) | 144 pages (avantages des zones 1 et 2) | — |
| SICAD | 127 extraits seulement (table `chatbot_sources` de la base AFI) | Le site interdit les robots : pas de collecte complète. |
| APIA | 5 extraits (table `chatbot_sources`) | Site non collecté. |
| **INS** (statistiques) | — | **Cité seulement, par choix du cahier des charges** (site protégé par CAPTCHA) : Dalila donne son rôle et son lien, sans lire ses chiffres. |
| **Ministères** | — | **Cités seulement**, comme l'INS (cahier des charges, section VI.6). |

## 5. Contradictions dans les textes de l'AFI

| Sujet | Ce qu'on trouve | À utiliser |
|---|---|---|
| Téléphone | Réponse 3 de la base de connaissances : chiffres dans le désordre. | **Corrigé** (voir DESACCORDS.md) : +216 71 124 260 (relations avec le citoyen), +216 71 124 242 (affaires commerciales), page contact du site AFI. |
| Date de création de l'AFI | 1973 ou 1974 selon les réponses ; le site de l'AFI lui-même dit « 1974 » sur ses pages des zones. | **14 avril 1973** : date précise de la page « L'agence » du site AFI (fr, en, ar) et du mot du PDG. |
| Nombre de zones et d'entreprises | 100 ou 115 zones, plus de 5 000 ou de 6 000 entreprises. | Citer la réponse avec sa date, ou le site AFI (environ 100 zones, plus de 3 000 ha, plus de 5 000 entreprises). |

## 6. Langues

- Les réponses validées de l'AFI sont presque toutes en français : traduire la présentation, jamais les chiffres.
- Traductions des familles du graphe en allemand et turc : écrites par Claude, **à relire**
  (graphe nommé `a-valider`).

## 7. Agent (Qwen3-4B sur processeur)

- 23 réponses justes sur 35 au banc d'essai ; erreurs restantes du modèle : des questions sur l'AFI prises pour hors
  sujet, un lieu réécrit au lieu d'être recopié, le mauvais outil pour un cahier des charges, un nom d'outil écrit au
  lieu d'être appelé (le harnais répond alors par le repli, avec le contact de l'AFI).
- Démarches demandées en allemand ou en turc : réponse en partie en français (les réponses de l'AFI sont en français).
- Jeu de test surtout en français (49 questions sur 57) : allemand et turc vérifiés à la main
  seulement.
- Ajustement du modèle en cours (Kaggle) : adopté seulement s'il fait mieux au même banc d'essai.

## 8. Voix

- Dialectes : le tunisien est transcrit par un modèle tunisien (38 % de mots faux sur de vrais extraits, contre 69 %
  pour Whisper seul). L'algérien et le libyen ne sont plus proposés (2026-11-28) : parlés, ils sont transcrits par le
  modèle tunisien, sans garantie (mesuré avant l'abandon : 93 % de mots faux en algérien, 46 % en libyen).
- Une phrase de plus de 6 à 8 s en tunisien peut dépasser 4 s de reconnaissance (deux modèles : détection, puis
  transcription).
- Noms de lieux dits dans une phrase anglaise, allemande ou turque : parfois mal reconnus (« Sousse » -> « sauce »).
  Le texte reconnu est affiché et modifiable avant l'envoi : l'interface doit garder cette étape.
- Arabizi : pas de voix de lecture ; la réponse reste en texte.
- Mesures faites avec des voix de synthèse ; à refaire sur de vrais enregistrements (`eval/voix_bench.py --dossier`).
