# Ce qui manque, et ce que Dalila doit dire

Ce qui est **absent de toutes nos sources** (les erreurs, elles, sont corrigées : voir `db/corrections/DESACCORDS.md`).
Vérifié le 2026-11-27 sur `afi.sql`, la carte publique actuelle de l'AFI (zones, lots, documents, indicateurs), les sites
officiels collectés et le corpus. Quand une information manque, Dalila le dit et renvoie vers l'AFI, au lieu de deviner.

## 1. Données de l'AFI

| Manque | Zones / détail | Ce que Dalila dit |
|---|---|---|
| **Prix non publié** | Gabès I, II et III ; Sousse I ; Sousse II ; Hstaftimi (prix 0 dans la base et sur la carte de l'AFI) ; Bir El Kassaa 2 (2022 DT/m² dans la base : impossible, masqué). | « Prix non publié par l'AFI », avec le contact de la direction commerciale (+216 71 124 242). |
| **Surface totale absente** | Bir El Kassaa 2, Kasserine Extention, Bouficha 2 (0 dans la base et sur la carte de l'AFI). Le site de l'AFI donne « Bouficha 30 ha » et « Kasserine 54 ha » sans dire de quelle tranche il s'agit : pas utilisé. | « Surface non publiée ». |
| **Surface aménagée** | Dans 43 zones sur 50, les lots ensemble dépassent ce chiffre : il ne mesure pas toute la partie lotie. | La citer telle quelle, sans rien en calculer. |
| **Enchères** | Ni la base ni la carte de l'AFI ne donnent de dates ou de mise à prix (champs vides). | Expliquer la procédure (réponses validées de l'AFI) ; renvoyer vers l'AFI pour les dates. |
| **Plans de lotissement** | ~~Aucun plan publié~~ **Réglé** : la carte de l'AFI publie les 45 plans de sa table `zone_documents` (30 zones visibles), vue `v_pub_plans`. Les 20 autres zones visibles n'ont pas de plan dans la base. | Donner le lien du plan quand il existe. |
| **Groupe 1 ou 2 du développement régional** | ~~La base dit seulement oui / non~~ **Réglé** : groupe de chaque zone d'après la carte de la FIPA (décret 2017-389), `db/reference/groupes_developpement_regional.csv` : 3 zones en groupe 1 (El Hancha, Menzel Chekir, Zriba 4), 27 en groupe 2. | Citer les avantages du groupe de la zone (TIA, FIPA) avec leur source, sans calculer de montant pour le projet. |
| **Équipements non renseignés** | Valeur 0 dans la base (34 zones pour le gaz, El Hancha pour tout) ; gazoducs nommés par une route (« RN … », 9 zones). | Non montrés : « information non disponible ». |
| **Lot à confirmer** | Lot 7204 (Sbikha 2) : disponible dans `afi.sql`, absent de la carte actuelle de l'AFI. | « Disponible selon la base, à confirmer auprès de l'AFI ». |

## 2. Services de l'AFI (BF23)

Vérifié le 2026-11-27 sur les réponses validées de l'AFI (12 à 25) et ses pages « Nos services » (fr, en, ar) : les 8
services ont leurs conditions ou étapes, leurs pièces et le lien de la source. Ce que l'AFI **ne publie pas** (détail
par service : `db/reference/services_afi.csv`) :

| Manque | Services | Ce que Dalila dit |
|---|---|---|
| Montant des frais de rédaction du contrat et de délimitation topographique | Acquisition d'un lot | « Montant non publié par l'AFI » (le cahier des charges interdit toute estimation de frais). |
| Frais de l'AFI | Autorisation de vente (leasing) | Seuls les frais du GMG sont cités : le dire. |
| Montant de la garantie, dates des ventes | Enchères | Fixés dans le cahier des charges de chaque vente : renvoyer vers l'AFI. |
| Lieu de dépôt | Les 6 services administratifs (attestations, acte de précision, autorisation, copie) | Ce que dit la source : « demande écrite adressée au PDG de l'AFI », avec l'adresse du siège et le bureau des relations avec le citoyen (+216 71 124 260) pour confirmer. Pas de lieu supposé. |

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
  À demander à l'AFI.
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
- Traductions des familles du graphe en allemand, turc, algérien et libyen : écrites par Claude, **à relire**
  (graphe nommé `a-valider`).
