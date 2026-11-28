-- Comptes et sessions (connexion de l'administrateur de l'AFI ; plus tard, des promoteurs).
-- Mot de passe : jamais en clair, seulement son empreinte scrypt (sel propre à chaque compte).
-- Session : un jeton aléatoire remis au navigateur dans un cookie HttpOnly ; la base n'en garde que l'empreinte SHA-256,
-- si bien qu'une copie de la base ne permet pas de se connecter. Le rôle est relu ici à chaque requête : rien dans le
-- jeton ne dit qui est administrateur, il n'y a donc rien à modifier côté navigateur.
CREATE TABLE IF NOT EXISTS agent_comptes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  identifiant VARCHAR(80) NOT NULL UNIQUE,
  nom VARCHAR(120) NULL,
  role VARCHAR(20) NOT NULL,
  mot_de_passe VARCHAR(255) NOT NULL,
  actif TINYINT NOT NULL DEFAULT 1,
  echecs INT NOT NULL DEFAULT 0,
  bloque_jusqu_a TIMESTAMP NULL,
  cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  derniere_connexion TIMESTAMP NULL,
  mot_de_passe_change_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS agent_jetons (
  empreinte CHAR(64) PRIMARY KEY,
  compte_id INT NOT NULL,
  cree_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expire_le TIMESTAMP NOT NULL,
  vu_le TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (compte_id),
  FOREIGN KEY (compte_id) REFERENCES agent_comptes (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

GRANT SELECT, INSERT, UPDATE ON afi.agent_comptes TO 'dalila_rw'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON afi.agent_jetons TO 'dalila_rw'@'%';
