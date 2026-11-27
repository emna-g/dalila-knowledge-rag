# Module sources (fraîcheur des données)

Relit chaque semaine les sources officielles de la configuration (pages et PDF), détecte ce qui a changé, et fait
passer les changements **relus et validés** jusqu'à Dalila (passages, vecteurs, graphe), avec les tests en barrière.
Le texte d'une page est une donnée, jamais une instruction ; en cas d'échec, la dernière version reste utilisée.
Décision : docs/decisions.md, « Fraîcheur des données ».

| | |
|---|---|
| **Exigences** | BF14, BF15, BNF14, BNF15 |
| **Contrat** | Liste fermée `config_sources.csv` ; état dans `agent_source_status` (compte `dalila_rw`) ; corpus `donnees/corpus/passages.jsonl`, puis `charger` → `vectoriser` → `construire_abox` → tests des outils. |
| **Hors lecture** | carte.afi.nat.tn (CAPTCHA : `rafraichir_copie_afi`, à la main), INS (cité seulement), SICAD et UNCTAD (robots.txt l'interdit). |
| **État** | Fait et testé le 2026-11-27 : 13 tests sans Internet ni base ; lecture réelle des 993 sources actives (991 lues, 2 pages de l'APII en erreur serveur 500/503 ; 601 Mo, environ 25 min la première fois) ; application de bout en bout sur la base (corpus → charger → construire_abox → tests des outils : réussie, puis remise en état). Limites : voir plus bas. |

## Le cycle d'une source

```
lecture chaque semaine ──> empreinte identique ───────────────> rien (date de lecture mise à jour)
                     └──> empreinte différente ──> « à relire » (rapport + différence ligne par ligne)
                                                     │  la version validée reste celle de Dalila
                          relecture humaine : rafraichir --valider URL
                                                     │
                          appliquer : corpus -> charger -> vectoriser -> construire_abox -> tests
                                         └── un test échoue : corpus d'avant remis et rechargé
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `config_sources.csv` | La liste **fermée** des URL relues (BNF14) : organisme, type, délai en jours, `actif` (0 = jamais lue), qui l'utilise. Se corrige à la main. |
| `inventaire.py` | Relève les URL citées par Dalila (`db/reference/*.csv` et corpus) ; ajoute les nouvelles ; passe à `actif = 0` celles qui ne sont plus citées. |
| `lire.py` | Lit une URL : une requête par seconde et par site, robots.txt respecté, CAPTCHA = arrêt du site (jamais contourné), redirection vers un autre site refusée, réponse 304 comprise. Page : contenu principal, sans menus ni en-têtes / pieds de page, encodage de la page respecté. PDF : lu par morceaux, texte extrait page par page ; PDF scanné signalé. |
| `empreinte.py` | Empreinte SHA-256 du texte normalisé (page) ou des octets (PDF). |
| `rafraichir.py` | Relit les sources dues, compare à la version validée : inchangée, changée (« à relire »), échec, disparue ; rapport, alertes ; `--valider`. |
| `decoupage.py` | Découpe un texte en passages comme la fusion (~1 400 caractères, pages, articles). |
| `appliquer.py` | Remplace dans le corpus les passages des sources validées, puis charger, vectoriser, construire_abox, tests ; retour arrière si échec ; sauvegarde du corpus et journal. |
| `base.py` | Recopie l'état dans `agent_source_status`. |
| `hebdo.py` | Les trois en une commande (à planifier) : relire, recopier l'état, appliquer ce qui est validé. |
| `scripts/rafraichir_sources.bat` | Lancement planifié sous Windows (la commande `schtasks` est dans le fichier ; cron pour Linux aussi). |

Hors git (comme les données) : `donnees/sources/etat.json`, `textes/` (version lue et version validée de chaque source),
`rapports/`, `journal_appliquer.jsonl` ; `donnees/corpus/sauvegardes/` (corpus d'avant chaque application).

## Commandes

```
python -m dalila.sources.hebdo                         chaque semaine (planifié) : relire, état en base, appliquer le validé
python -m dalila.sources.rafraichir                    voir ce qui a changé sans rien enregistrer
python -m dalila.sources.rafraichir --valider URL      après relecture : le changement devient la version validée
python -m dalila.sources.appliquer                     voir ce qui sera appliqué ; --appliquer pour le faire
python -m dalila.sources.inventaire --ecrire           mettre la liste à jour (nouvelles URL citées)
python -m tests.sources.test_sources                   tests (serveur web local, sans Internet ni base)
```

Le rapport de chaque semaine dit, pour une source changée, quels fichiers l'utilisent : si c'est un fichier de
`db/reference/` (prix du site, groupes FIPA…), la valeur se corrige à la main dans ce fichier, puis `charger`.

## Limites connues

- **Première lecture longue** : environ 25 minutes et 600 Mo ; les suivantes ne retéléchargent pas un fichier inchangé quand le site le permet (réponse 304). L'état est enregistré toutes les 20 sources : un arrêt de l'ordinateur ne perd pas le travail fait.

- **Cahiers des charges scannés** : 70 des 138 PDF lus sont des images (63 de l'AFI, 6 de la FIPA, 1 de l'APII). Un changement est détecté (empreinte
  du fichier) mais leur texte demande un OCR : ils restent « en attente » après validation, signalés dans le rapport.
- **Pages sans `<main>`** (APII, TIA, une partie de la FIPA) : des menus restent dans le texte ; un changement de menu
  peut donc donner une fausse alerte « à relire » (sans effet sur Dalila tant qu'elle n'est pas validée).
- **Données de l'AFI** (lots, prix, disponibilité) : hors de ce module ; `rafraichir_copie_afi` à la main (CAPTCHA),
  ou mieux un export ou un accès fourni par l'AFI.
