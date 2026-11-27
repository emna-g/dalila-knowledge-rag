# Module sources

Lit les URL de la configuration (et leurs PDF), garde les extraits avec leur lien, au moins chaque semaine ; état de chaque URL (dernière lecture, échec, relance). Le texte d'une page est une donnée, jamais une instruction ; en cas d'échec, la dernière version reste utilisée.

Fraîcheur (voir docs/decisions.md, « Fraîcheur des données ») : date de consultation et empreinte de contenu pour chaque passage et chaque ligne de `db/reference/` ; seuls les passages changés sont revectorisés ; un texte changé passe en « à relire » avant de remplacer une version validée ; reconstruction du graphe puis tests des outils après chaque rafraîchissement.

| | |
|---|---|
| **Exigences** | BF14, BF15, BNF14 |
| **Contrat** | Table `agent_source_status` (déjà créée). INS, ministères et site AFI : cités seulement (protégés par CAPTCHA). |
| **S'appuie sur** | base MariaDB (dalila_passages, dalila_sources) |
| **État** | À faire. |
