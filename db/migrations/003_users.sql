-- Deux comptes : dalila_ro lit seulement les vues publiques et les passages ; dalila_rw écrit les tables agent_*.
-- Les mots de passe viennent du fichier .env (jamais dans git) : ce script est lancé par backend/ingest/migrer.py,
-- qui remplace :RO_PASSWORD et :RW_PASSWORD.
CREATE USER IF NOT EXISTS 'dalila_ro'@'%' IDENTIFIED BY ':RO_PASSWORD';
CREATE USER IF NOT EXISTS 'dalila_rw'@'%' IDENTIFIED BY ':RW_PASSWORD';
GRANT SELECT ON afi.v_pub_lots TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_lots_disponibles TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_zones TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_zone_distances TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_zone_equipements TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_services_proches TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_cahiers TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_lot_polygones TO 'dalila_ro'@'%';
GRANT SELECT ON afi.dalila_passages TO 'dalila_ro'@'%';
GRANT SELECT ON afi.dalila_sources TO 'dalila_ro'@'%';
GRANT SELECT ON afi.dalila_gouvernorats TO 'dalila_ro'@'%';
GRANT SELECT ON afi.chatbot_connaissances TO 'dalila_ro'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_sessions TO 'dalila_rw'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_turns TO 'dalila_rw'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_needs TO 'dalila_rw'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_learning_candidates TO 'dalila_rw'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_learning_journal TO 'dalila_rw'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.agent_source_status TO 'dalila_rw'@'%';
FLUSH PRIVILEGES;
