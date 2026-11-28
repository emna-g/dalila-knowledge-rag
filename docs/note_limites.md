# Dalila : limites connues et travail avant la mise en production (livrable 5)

Note d'une page, 2026-11-28. Chiffres : [mesures.md](mesures.md) ; détail des manques : [limites.md](limites.md).

Dalila répond en 8 langues, sur processeur seul, en moins de 35 s, avec des chiffres vérifiés contre la base de l'AFI.
Voici ce qui la limite aujourd'hui, ce que ça change pour le visiteur, et ce qui le corrigerait.

| # | Limite | Effet pour le visiteur | Ce qui la corrigerait |
|---|---|---|---|
| 1 | **L'agent se trompe encore une fois sur trois** (22 bonnes réponses sur 35 ; nombre de lots juste 10 fois sur 16). Il prend parfois une question sur les démarches pour une question sur les lots, ou lit mal un nombre (une surface prise pour un prix). | Réponse à côté ou incomplète. Jamais de chiffre inventé : le harnais bloque tout nombre absent de la base et renvoie alors vers l'AFI. | Un second ajustement du modèle avec plus d'exemples de démarches (73 sur 816 aujourd'hui) et de nombres à lire (surface, prix, budget, pourcentage), et les vraies conversations exportées. |
| 2 | **Algérien parlé mal reconnu** (93 % de mots faux) ; le tunisien à 38 %. | Le visiteur doit corriger le texte reconnu, toujours affiché avant l'envoi. | Ajuster Whisper sur le corpus algérien CAFE (35 h, ouvert) et sur les jeux tunisiens ouverts. |
| 3 | **Pas de voix tunisienne** : le tunisien est lu par une voix arabe standard (ce qui est signalé au visiteur). | Lecture compréhensible, mais pas dans le dialecte. | Évaluer TunArTTS (Apache 2.0), qui demande d'ajouter les voyelles au texte. |
| 4 | **Données absentes à la source** : 14 zones sans cahier des charges, 2 zones sans prix, dates et mise à prix des enchères vides. | Dalila dit que l'information n'est pas publiée et donne le contact de l'AFI. | L'AFI publie les cahiers (dont celui d'Om Laatham), les prix et les dates des ventes. |
| 5 | **Tests surtout en français** (49 vraies questions sur 57) ; plusieurs tests d'acceptation du cahier pas encore lancés (BF2, BF17, BNF13, BNF14). | Qualité moins sûre en allemand, turc et dialectes ; traductions de l'allemand et du turc à relire. | Un jeu de test dans les 8 langues, relu par des locuteurs, et les tests d'acceptation passés avant la livraison. |
| 6 | **Pas d'écrans d'administration** : questions mal traitées, journal de l'apprentissage (avec « Annuler »), état des sources. | Aucun pour le visiteur ; l'agent de l'AFI doit passer par des commandes. | Des routes de lecture dans l'API, puis 3 écrans (les données sont déjà prêtes). |
| 7 | **Le micro exige HTTPS** ; aujourd'hui, le service tourne en local. | Sans HTTPS, pas de questions à la voix en production. | Certificat et Nginx sur le serveur de l'AFI. |
| 8 | **Demande d'acquisition et conversation vocale continue** (BF11, BF13, souhaités) pas encore faites. | Le visiteur prépare son dossier seul ; il appuie sur le micro à chaque question. | Formulaire prérempli depuis la conversation, avec confirmation obligatoire ; micro rouvert après chaque réponse. |

**Avant la mise en production, dans l'ordre** : HTTPS (7), tests d'acceptation et relecture des langues (5), second
ajustement de l'agent (1), écrans d'administration (6). Les points 2, 3 et 8 améliorent l'usage mais ne bloquent pas
l'ouverture.
