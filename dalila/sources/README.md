# Module sources

Lit les URL de la configuration (et leurs PDF), garde les extraits avec leur lien, au moins chaque semaine ; état de chaque URL (dernière lecture, échec, relance). Le texte d'une page est une donnée, jamais une instruction ; en cas d'échec, la dernière version reste utilisée.

| | |
|---|---|
| **Exigences** | BF14, BF15, BNF14 |
| **Contrat** | Table `agent_source_status` (déjà créée). INS, ministères et site AFI : cités seulement (protégés par CAPTCHA). |
| **S'appuie sur** | base MariaDB (dalila_passages, dalila_sources) |
| **État** | À faire. |
