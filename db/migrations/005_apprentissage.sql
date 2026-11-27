-- Noms de lieux appris des conversations (BF18, BF19, BF21) : à part des alias venus des sources de l'AFI
-- (dalila_zone_alias), révocables un par un. Jamais un chiffre ni une condition : seulement « ce nom désigne ce lieu ».
CREATE TABLE IF NOT EXISTS agent_appris_lieux (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  alias VARCHAR(150) NOT NULL,
  type VARCHAR(20) NOT NULL,            -- zone ou gouvernorat
  cible_id VARCHAR(20) NOT NULL,
  candidat_id BIGINT,
  actif TINYINT NOT NULL DEFAULT 0,
  modifie_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY (alias, type, cible_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
GRANT SELECT ON afi.agent_appris_lieux TO 'dalila_ro'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_appris_lieux TO 'dalila_rw'@'%';
