-- Additive repair for reference tables and public view contracts.
-- Reference rows are synchronized separately from the canonical db/reference CSV files.
-- Existing public views stay untouched; new consumers use versioned *_v2 views.
-- It executes no DROP, DELETE FROM, TRUNCATE, or AFI-table writes.

CREATE TABLE IF NOT EXISTS dalila_gouvernorats (
  code INT PRIMARY KEY,
  nom_fr VARCHAR(80),
  nom_ar VARCHAR(80),
  source VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_zone_alias (
  zone_id VARCHAR(20),
  alias VARCHAR(150),
  langue VARCHAR(5),
  source VARCHAR(255),
  PRIMARY KEY (zone_id, alias)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_zone_groupe_dr (
  zone_id VARCHAR(20) PRIMARY KEY,
  groupe TINYINT,
  delegation VARCHAR(80),
  source VARCHAR(500)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_lots_a_confirmer (
  lot_id INT PRIMARY KEY,
  etape_afi INT,
  raison VARCHAR(255),
  source VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_prix_publies (
  zone_id VARCHAR(20) PRIMARY KEY,
  prix_m2_dt DOUBLE,
  source VARCHAR(500),
  date_source DATE NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
ALTER TABLE dalila_prix_publies ADD COLUMN IF NOT EXISTS date_source DATE NULL;

CREATE TABLE IF NOT EXISTS dalila_zone_surface_contours (
  zone_id VARCHAR(20) PRIMARY KEY,
  surface_m2 DOUBLE,
  nb_contours INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_prix_site (
  zone_id VARCHAR(20) PRIMARY KEY,
  nom_sur_la_page VARCHAR(100),
  prix_m2_dt DOUBLE,
  prix_m2_subventionne_dt DOUBLE,
  source VARCHAR(500),
  date_source DATE NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
ALTER TABLE dalila_prix_site ADD COLUMN IF NOT EXISTS date_source DATE NULL;

CREATE TABLE IF NOT EXISTS dalila_echantillon_eval (
  id VARCHAR(12) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE USER IF NOT EXISTS 'dalila_ingest'@'%' IDENTIFIED BY ':INGEST_PASSWORD';

CREATE OR REPLACE VIEW v_pub_lots_v2 AS
SELECT d.lot_id, d.zone_id, z.nom_fr AS zone_fr, d.lot_num, d.surface_m2, e.statut, e.libelle_carte,
       IF(a.lot_id IS NULL, 0, 1) AS a_confirmer, z.prix_m2_dt, d.source_statut,
       IF(z.prix_m2_dt IS NULL, pp.prix_m2_dt, NULL) AS prix_m2_dernier_publie_dt,
       IF(z.prix_m2_dt IS NULL, pp.source, NULL) AS prix_dernier_publie_source,
       IF(z.prix_m2_dt IS NULL, pp.date_source, NULL) AS prix_dernier_publie_date_source
FROM v_dalila_lots d
JOIN v_dalila_zones z ON z.zone_id = d.zone_id
LEFT JOIN dalila_prix_publies pp ON pp.zone_id = d.zone_id
JOIN dalila_etape_statut e ON e.etape = d.etape
LEFT JOIN dalila_lots_a_confirmer a ON a.lot_id = d.lot_id AND a.etape_afi = d.etape
WHERE z.visible = 1 AND d.surface_m2 > 0 AND d.nature = 1;

CREATE OR REPLACE VIEW v_pub_lots_disponibles_v2 AS
SELECT lot_id, zone_id, zone_fr, lot_num, surface_m2, statut, libelle_carte, a_confirmer, prix_m2_dt,
       source_statut, prix_m2_dernier_publie_dt, prix_dernier_publie_source, prix_dernier_publie_date_source
FROM v_pub_lots_v2
WHERE statut = 'disponible';

CREATE OR REPLACE VIEW v_pub_zones_v2 AS
SELECT z.zone_id, z.nom_fr, z.nom_ar, g.nom_fr AS gouvernorat_fr, g.nom_ar AS gouvernorat_ar,
       z.gouvernorat_code, z.lat, z.lng, z.surface_totale_m2, z.surface_amenagee_m2, z.prix_m2_dt,
       z.zone_developpement_regional,
       IF(z.zone_developpement_regional = 1, gr.groupe, NULL) AS groupe_developpement_regional,
       IF(z.prix_m2_dt IS NULL, pp.prix_m2_dt, NULL) AS prix_m2_dernier_publie_dt,
       IF(z.prix_m2_dt IS NULL, pp.source, NULL) AS prix_dernier_publie_source,
       IF(z.surface_amenagee_m2 IS NULL, sc.surface_m2, NULL) AS surface_amenagee_calculee_m2,
       ps.prix_m2_dt AS prix_m2_site_afi_dt,
       ps.prix_m2_subventionne_dt AS prix_m2_subventionne_site_afi_dt,
       ps.source AS prix_site_afi_source,
       IF(ps.prix_m2_dt IS NOT NULL AND z.prix_m2_dt IS NOT NULL AND ps.prix_m2_dt <> z.prix_m2_dt,
          1, 0) AS prix_en_conflit,
       CAST(COALESCE(n.disponibles, 0) AS SIGNED) AS lots_disponibles,
       CAST(COALESCE(n.disponibles_a_confirmer, 0) AS SIGNED) AS lots_disponibles_a_confirmer,
       CAST(COALESCE(n.encheres, 0) AS SIGNED) AS lots_mis_aux_encheres,
       IF(z.prix_m2_dt IS NULL, pp.date_source, NULL) AS prix_dernier_publie_date_source,
       ps.date_source AS prix_site_afi_date_source
FROM v_dalila_zones z
LEFT JOIN dalila_gouvernorats g ON g.code = z.gouvernorat_code
LEFT JOIN dalila_zone_groupe_dr gr ON gr.zone_id = z.zone_id
LEFT JOIN dalila_prix_publies pp ON pp.zone_id = z.zone_id
LEFT JOIN dalila_zone_surface_contours sc ON sc.zone_id = z.zone_id
LEFT JOIN dalila_prix_site ps ON ps.zone_id = z.zone_id
LEFT JOIN (
  SELECT zone_id,
         SUM(statut = 'disponible') AS disponibles,
         SUM(statut = 'disponible' AND a_confirmer = 1) AS disponibles_a_confirmer,
         SUM(statut = 'mis_aux_encheres') AS encheres
  FROM v_pub_lots_v2
  GROUP BY zone_id
) n ON n.zone_id = z.zone_id
WHERE z.visible = 1;

GRANT SELECT ON afi.v_pub_lots_v2 TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_lots_disponibles_v2 TO 'dalila_ro'@'%';
GRANT SELECT ON afi.v_pub_zones_v2 TO 'dalila_ro'@'%';
GRANT SELECT ON afi.dalila_cahiers TO 'dalila_ro'@'%';
GRANT SELECT (contenu) ON afi.chatbot_sources TO 'dalila_ro'@'%';

GRANT SELECT ON afi.v_pub_lots TO 'dalila_ingest'@'%';
GRANT SELECT ON afi.v_pub_lots_disponibles TO 'dalila_ingest'@'%';
GRANT SELECT ON afi.v_pub_zones TO 'dalila_ingest'@'%';
GRANT SELECT ON afi.v_pub_zone_distances TO 'dalila_ingest'@'%';
GRANT SELECT ON afi.v_dalila_corrections_etat TO 'dalila_ingest'@'%';
GRANT SELECT ON afi.chatbot_connaissances TO 'dalila_ingest'@'%';
GRANT SELECT ON afi.lots_kml TO 'dalila_ingest'@'%';

GRANT SELECT, INSERT, UPDATE ON afi.dalila_gouvernorats TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_corrections TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_lots_a_confirmer TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_zone_alias TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_zone_groupe_dr TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_prix_publies TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_prix_site TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_zone_surface_contours TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_cahiers TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_sources TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, UPDATE ON afi.dalila_passages TO 'dalila_ingest'@'%';
GRANT SELECT, INSERT, DELETE ON afi.dalila_echantillon_eval TO 'dalila_ingest'@'%';
