# Désaccords entre les sources, et décisions

Produit par `python -m dalila.connaissances.extraire_corrections`. Dalila lit la base AFI en direct ; chaque ligne est une correction de `dalila_corrections.csv`. Pour changer une décision : colonne `appliquee`, puis `python -m dalila.connaissances.charger`.

## Les sources

| Source | Ce que c'est |
|---|---|
| Base AFI (`afi.sql`) | Les tables de l'AFI, lues en direct par Dalila. |
| Carte actuelle de l'AFI | carte.afi.nat.tn, relevée le 2026-11-26 (`carte_afi_actuelle.json`, par `dalila.connaissances.lire_carte_afi`). Elle lit la base de l'AFI. |
| Ancienne carte | afi.e-industrie.gov.tn, relevée le 2026-11-25 pour la fusion. |

Accord entre la carte actuelle et la base : zones 250 / 250, commodites 528 / 528, lots 2955 / 2958. La carte actuelle donne donc les valeurs de la base ; c'est l'ancienne carte qui diffère (noms, prix, surfaces, distances). Nos propres contrôles (GPS, contours des lots, site de l'AFI) donnent tort à l'ancienne carte chaque fois qu'ils permettent de trancher.

## Règles de décision

1. **Les données actuelles de l'AFI l'emportent** (base, ou carte actuelle quand l'AFI a changé une valeur depuis l'export).
2. **Ancienne carte :** gardée pour mémoire, non appliquée. Exceptions : orthographe des noms de distances (Ennfidha → Enfidha…). Ses noms de zones (« ENFIDHA 2 », « KASSERINE 2 »…) deviennent des **noms alternatifs** : reconnus dans les questions, mais Dalila affiche le nom de l'AFI.
3. **Prix impossible** (plus de 500 DT/m²) : masqué, Dalila dit « prix non publié ». Prix à 0 : « prix non publié par l'AFI » (Gabès, Sousse I et II, Hstaftimi).
4. **Réponses de la base de connaissances AFI :** relues en direct ; une erreur prouvée (numéro de téléphone mal écrit) est corrigée par extrait, tant que l'extrait faux s'y trouve encore.
5. **Zone sans distances** dans la base : distances de la zone voisine à moins de 1 km (Kasserine Extention ← Kasserine, à 0,4 km).
6. **Lot disponible dans la base mais pas sur la carte actuelle :** gardé, avec « à confirmer auprès de l'AFI ».

## Règles d'affichage (vues `v_pub_*`)

- Seuls les lots **cessibles** (`LOT_NATURE` = 1) sont listés : c'est la règle de la carte de l'AFI. Les autres (équipements publics, voirie…) ne sont pas à vendre.
- Équipement à **0** (électricité, eau, gaz, téléphone) : non montré ; 0 veut dire « non renseigné ».
- Gazoduc nommé par une route (« RN … ») : non montré (la base et la carte actuelle donnent une route ; la valeur n'est pas fiable).
- Contour de lot dont l'aire n'est pas entre 2/3 et 1,5 fois la surface du lot : non dessiné.
- Distance à **0 km** : à dire « à moins d'un kilomètre ».
- Surface aménagée : citée telle que l'AFI la donne, sans calcul. La surface totale de la base est celle du site de l'AFI (page « المناطق المهيئة »).
- Enchères : ni la base ni la carte actuelle ne donnent de dates ou de mise à prix (champs vides).

## Corrections appliquées (28)

| Élément | Champ | Base AFI | Autre valeur | Source de l'autre valeur | Raison |
|---|---|---|---|---|---|
| Réponse AFI n° 3 | reponse (extrait) | +216 260 124 71 | +216 71 124 260 | page contact du site de l'AFI (afi.nat.tn/fr/contact) : bureau des relations avec le citoyen (216+) 71124260 ; même numéro que la réponse 26 | chiffres du numéro dans le désordre dans la réponse de l'AFI |
| Réponse AFI n° 3 | reponse (extrait) | +216 242 124 71 | +216 71 124 242 | page contact du site de l'AFI (afi.nat.tn/fr/contact) : direction des affaires commerciales (216+) 71124242 | chiffres du numéro dans le désordre dans la réponse de l'AFI |
| Lot 4138 | LOT_ETAPE | 4 | 5 | carte publique actuelle de l'AFI carte.afi.nat.tn (relevée le 2026-11-26) | étape changée par l'AFI depuis l'export afi.sql (« Non disponible » sur la carte actuelle) |
| Lot 4427 | LOT_ETAPE | 2 | 4 | carte publique actuelle de l'AFI carte.afi.nat.tn (relevée le 2026-11-26) | étape changée par l'AFI depuis l'export afi.sql (« Mis aux enchères » sur la carte actuelle) |
| Lot 6932 | LOT_ETAPE | 4 | 2 | carte publique actuelle de l'AFI carte.afi.nat.tn (relevée le 2026-11-26) | étape changée par l'AFI depuis l'export afi.sql (« Réservé » sur la carte actuelle) |
| Distance 9302051 BIR EL KASSAA 2 → aeroport | zc_distance | — | 18.00 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → aeroport | zc_libelle_francais | — | Tunis Carthage | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → port | zc_distance | — | 19.00 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → port | zc_libelle_francais | — | La Goulette | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → gare | zc_distance | — | 1.00 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → gare | zc_libelle_francais | — | Bir Kassaa | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → autoroute | zc_distance | — | 1.00 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → autoroute | zc_libelle_francais | — | A1 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → gazoduc | zc_distance | — | 4.00 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 9302051 BIR EL KASSAA 2 → gazoduc | zc_libelle_francais | — | GP1 | base AFI, zone voisine 930204 BIR EL KASSAA 3 (à 0.6 km) | zone sans distances dans la base : valeurs de la zone voisine |
| Distance 930920 Bouficha 2 → aeroport | zc_libelle_francais | Ennfidha | Enfidha | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | correction d'orthographe |
| Distance 930920 Bouficha 2 → gazoduc | zc_libelle_francais | GP1 | GP 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | correction d'orthographe |
| Distance 931100 Tataouine el khabta → aeroport | zc_libelle_francais | Jerba | Djerba | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | correction d'orthographe |
| Distance 931103 Tejra Mednibe Tranche 1 → aeroport | zc_libelle_francais | Jerba | Djerba | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | correction d'orthographe |
| Distance 931300 KASSERINE Extention → aeroport | zc_distance | — | 200.00 | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → aeroport | zc_libelle_francais | — | Thyna | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → port | zc_distance | — | 204.00 | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → port | zc_libelle_francais | — | Sfax | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → gare | zc_distance | — | 3.00 | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → gare | zc_libelle_francais | — | Kasserine | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → autoroute | zc_distance | — | 191.00 | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Distance 931300 KASSERINE Extention → autoroute | zc_libelle_francais | — | A1 | base AFI, zone voisine 931301 KASSERINE (à 0.4 km) | zone sans distances dans la base : valeurs de la zone voisine (l'ancienne carte donne les mêmes) |
| Zone 9302051 BIR EL KASSAA 2 | prixunitaire | 2022 | — | contrôle Dalila (données AFI) | prix impossible (2022 DT/m², sans doute une année) : masqué, « prix non publié » |

## Lots à confirmer (1)

| Lot | Raison |
|---|---|
| 7204 | disponible dans la base (export afi.sql), mais absent de la carte actuelle de l'AFI |

## Noms alternatifs (12)

| Zone | Nom AFI (affiché) | Nom alternatif (reconnu) |
|---|---|---|
| 930607 | ENNFIDHA II | ENFIDHA 2 |
| 931009 | EL MAHRES | المحرس القسط الأول |
| 931103 | Tejra Mednibe Tranche 1 | Tejra Mednine |
| 931206 | Zriba 4 1 Tranche | Zriba 4 |
| 931206 | Zriba 4 1 Tranche | الزريبة 4 |
| 931208 | Beni khalled Borj Ettoumi | Beni khalled Sidi Ettoumi |
| 931300 | KASSERINE Extention | KASSERINE 2 |
| 931300 | KASSERINE Extention | القصرين 2 |
| 931301 | KASSERINE | KASSERINE 1 |
| 931301 | KASSERINE | القصرين 1 |
| 931704 | GAFOUR | GAAFOUR |
| 931706 | Bouarada II | بوعرادة 2 |

## Valeurs de l'ancienne carte non retenues (66)

| Élément | Champ | Base AFI | Autre valeur | Source de l'autre valeur | Raison |
|---|---|---|---|---|---|
| Lot 4380 | LOT_SUP_LOTIS | 4000 | 3676 | fusion, sans source | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; la surface de la fusion n'a pas de source |
| Lot 4381 | LOT_SUP_LOTIS | 3000 | 3523 | fusion, sans source | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; la surface de la fusion n'a pas de source |
| Distance 930607 ENNFIDHA II → aeroport | zc_distance | 3.00 | 68 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; l'aéroport d'Enfidha est à environ 3 km à vol d'oiseau : 68 km impossible |
| Distance 930607 ENNFIDHA II → gazoduc | zc_distance | 0.00 | 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 930920 Bouficha 2 → aeroport | zc_distance | 28.00 | 90 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; aéroport d'Enfidha à environ 23 km à vol d'oiseau : 90 km impossible |
| Distance 930920 Bouficha 2 → gare | zc_distance | 2.00 | 22 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931009 EL MAHRES → aeroport | zc_distance | 32.00 | 41 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931009 EL MAHRES → gare | zc_distance | 4.00 | 4.5 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931009 EL MAHRES → autoroute | zc_distance | 9.00 | 14 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931009 EL MAHRES → gazoduc | zc_libelle_francais | RN 1 | GP 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931011 MENZEL CHEKIR → gazoduc | zc_distance | 30.00 | 40 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931011 MENZEL CHEKIR → gazoduc | zc_libelle_francais | RN 1 | GP 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931100 Tataouine el khabta → port | zc_libelle_francais | Zarzis | Gabes | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Gabès est à 111 km à vol d'oiseau : 100 km par la route impossible |
| Distance 931103 Tejra Mednibe Tranche 1 → port | zc_libelle_francais | Zarzis | Gabes | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Gabès est à 67 km à vol d'oiseau : 65 km par la route impossible |
| Distance 931301 KASSERINE → gazoduc | zc_distance | 5.00 | 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931301 KASSERINE → gazoduc | zc_libelle_francais | RN13 | GP13 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931403 HAJEB LAAYOUN → gare | zc_libelle_francais | Sousse  Ezzouhor(Marchandise) | Enfidha | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931500 Jendouba El IRTIYEH → aeroport | zc_libelle_francais | Tabarka | Tunis Carthage | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Tunis-Carthage est à 125 km à vol d'oiseau : 79 km ne peut être que Tabarka |
| Distance 931500 Jendouba El IRTIYEH → gare | zc_distance | 15.00 | 149 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; la zone est à 11 km de la zone de Jendouba, dont la gare est à 5 km : 149 km impossible |
| Distance 931500 Jendouba El IRTIYEH → gare | zc_libelle_francais | Benbechir | Jendouba | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; la zone est à 11 km de la zone de Jendouba, dont la gare est à 5 km : 149 km impossible |
| Distance 931501 JENDOUBA → aeroport | zc_libelle_francais | Tabarka | Tunis Carthage | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Tunis-Carthage est à 130 km à vol d'oiseau : 85 km ne peut être que Tabarka |
| Distance 931501 JENDOUBA → gare | zc_distance | 5.00 | 161 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; zone dans Jendouba : 161 km impossible |
| Distance 9315043 TABARKA 2 → aeroport | zc_libelle_francais | Tabarka | Tunis Carthage | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Tunis-Carthage est à 125 km à vol d'oiseau : 17 km ne peut être que Tabarka |
| Distance 9315043 TABARKA 2 → gare | zc_distance | 65.00 | 188 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Tabarka 2 est à 51 km de la zone de Jendouba (gare à 5 km) : 188 km impossible |
| Distance 931704 GAFOUR → gare | zc_distance | 1.00 | 1.5 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931704 GAFOUR → autoroute | zc_distance | 50.00 | 64 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931704 GAFOUR → autoroute | zc_libelle_francais | A3 | A1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931705 MAKTHER → autoroute | zc_distance | 110.00 | 126 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931705 MAKTHER → autoroute | zc_libelle_francais | A3 | A1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931705 MAKTHER → gazoduc | zc_distance | 0.00 | 0.5 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931706 Bouarada II → gare | zc_distance | 3.00 | 3.5 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931706 Bouarada II → autoroute | zc_distance | 40.00 | 38 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931706 Bouarada II → autoroute | zc_libelle_francais | A3 | A1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931803 El Krib → gare | zc_libelle_francais | Gaafour | El Krib | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; El Krib est à 18 km de Gaafour, dont la gare est à 1 km : la gare de Gaafour à 16 km est cohérente |
| Distance 931803 El Krib → autoroute | zc_distance | 40.00 | 70 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931803 El Krib → autoroute | zc_libelle_francais | A3 | A1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 931900 LASSOUDA → gazoduc | zc_libelle_francais | RN13 | GP13 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 932108 Sbitla → gazoduc | zc_libelle_francais | RN13 | GP13 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 932114 Tozeur Kastilia → gare | zc_libelle_francais | Tozeur | Gabes | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; Gabès est à environ 168 km à vol d'oiseau : 3 km ne peut être que Tozeur |
| Distance 932114 Tozeur Kastilia → autoroute | zc_distance | 180.00 | 200 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Distance 932117 EL Golaa → gare | zc_libelle_francais | Gabes | Gafsa | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 88888 Gabes I & II & III | prixunitaire | 0 | 50 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 930211 Oueslatia | zone_sup_amenager | 71609 | 71301 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 930602 SOUSSE II | prixunitaire | 0 | 100 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 930606 BOUFICHA | prixunitaire | 0 | 100 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 930607 ENNFIDHA II | zone_libelle_francais | ENNFIDHA II | ENFIDHA 2 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 930900 sejnane | zone_sup_amenager | 229614 | 294369 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 930900 sejnane | zone_sup_total | 312254 | 150000 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; le site de l'AFI (page « المناطق المهيئة ») donne 31 ha, et les lots couvrent déjà plus de 150 000 m² |
| Zone 931009 EL MAHRES | zone_libelle_arabe | المحرس | المحرس القسط الأول | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931100 Tataouine el khabta | zone_sup_amenager | 73257 | 70429 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931103 Tejra Mednibe Tranche 1 | zone_libelle_francais | Tejra Mednibe Tranche 1 | Tejra Mednine | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931206 Zriba 4 1 Tranche | zone_libelle_arabe | الزريبة 4 القسط الأول | الزريبة 4 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931206 Zriba 4 1 Tranche | zone_libelle_francais | Zriba 4 1 Tranche | Zriba 4 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931208 Beni khalled Borj Ettoumi | zone_libelle_francais | Beni khalled Borj Ettoumi | Beni khalled Sidi Ettoumi | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931300 KASSERINE Extention | zone_libelle_arabe | القصرين توسعة | القصرين 2 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931300 KASSERINE Extention | zone_libelle_francais | KASSERINE Extention | KASSERINE 2 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931301 KASSERINE | zone_libelle_arabe | القصرين | القصرين 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931301 KASSERINE | zone_libelle_francais | KASSERINE | KASSERINE 1 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931704 GAFOUR | zone_libelle_francais | GAFOUR | GAAFOUR | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931706 Bouarada II | zone_libelle_arabe | بوعرادة 2 قسط اول | بوعرادة 2 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 931804 El Kef Extension | prixunitaire | 32 | 118 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base ; 118 DT/m² serait de loin le prix le plus élevé des zones de développement régional |
| Zone 931897 Jelma Sidi Bouzid | zone_sup_amenager | 108538 | 106274 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 932114 Tozeur Kastilia | zone_sup_amenager | 154172 | 151844 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 932119 Ras El Morj Monastir | prixunitaire | 70 | 90 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 932119 Ras El Morj Monastir | zone_sup_amenager | 316305 | 397260 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
| Zone 932132 Sbikha 2 | zone_sup_amenager | 814515 | 815191 | ancienne carte publique afi.e-industrie.gov.tn (relevée le 2026-11-25 pour la fusion) | non appliquée : la carte actuelle de l'AFI donne la valeur de la base |
