-- Synonymes appris des conversations (BF18, BF19, BF21) : un mot du visiteur -> une activité ou un secteur de
-- l'ontologie. Lus en direct par la recherche des activités, ajoutés au graphe (graphe nommé appris/<id>) à chaque
-- construction ; révocables un par un. Jamais un chiffre, une disponibilité ou une condition.
CREATE TABLE IF NOT EXISTS agent_appris_synonymes (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  terme VARCHAR(100) NOT NULL,
  concept_uri VARCHAR(300) NOT NULL,
  concept_libelle VARCHAR(300),
  candidat_id BIGINT,
  actif TINYINT NOT NULL DEFAULT 0,
  modifie_le TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY (terme, concept_uri)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
GRANT SELECT ON afi.agent_appris_synonymes TO 'dalila_ro'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_appris_synonymes TO 'dalila_rw'@'%';
