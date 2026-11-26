-- Tables ajoutées par Dalila À CÔTÉ du schéma de l'AFI (afi.sql est chargé tel quel, sans modification).
-- Règle : un chiffre n'est stocké qu'une fois. Les comptes (lots disponibles par zone…) ne sont PAS stockés :
-- ils sont calculés par les vues (002_views.sql).
-- Même interclassement (collation) que les tables de l AFI (utf8mb4_general_ci), pour pouvoir les joindre.
-- MariaDB 11.8 LTS (type VECTOR). Pour une base 10.11 : remplacer VECTOR(n) par BLOB (recherche numpy).

CREATE TABLE IF NOT EXISTS dalila_gouvernorats (
  code INT PRIMARY KEY, nom_fr VARCHAR(80), nom_ar VARCHAR(80), source VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Attributs de zone vérifiés (nom propre, prix retenu, présence sur la carte) avec leur source.
-- Les zones elles-mêmes restent dans la table AFI `zones`.
CREATE TABLE IF NOT EXISTS dalila_zones (
  zone_id VARCHAR(20) PRIMARY KEY, nom_fr VARCHAR(150), nom_ar VARCHAR(150), gouvernorat_code INT,
  lat DOUBLE, lng DOUBLE, surface_totale_m2 DOUBLE, surface_amenagee_m2 DOUBLE,
  prix_m2_dt DOUBLE NULL COMMENT 'NULL = prix non publié ; jamais 0',
  zone_developpement_regional TINYINT(1), sur_carte_en_ligne TINYINT(1), visible_dans_la_base TINYINT(1),
  source_prix VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_zone_distances (
  zone_id VARCHAR(20), type VARCHAR(30), nom VARCHAR(150), km DOUBLE, source VARCHAR(255),
  PRIMARY KEY (zone_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_zone_equipements (
  zone_id VARCHAR(20), type VARCHAR(40), valeur VARCHAR(80), unite VARCHAR(30), source VARCHAR(255),
  PRIMARY KEY (zone_id, type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_services_proches (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id VARCHAR(20), categorie VARCHAR(40), nom VARCHAR(255),
  distance_km DOUBLE, lat DOUBLE, lng DOUBLE, source VARCHAR(255), KEY (zone_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Statut décodé d'un lot (étape -> libellé des cartes de l'AFI), avec sa source et « à confirmer ».
CREATE TABLE IF NOT EXISTS dalila_lot_statut (
  lot_id INT PRIMARY KEY, zone_id VARCHAR(20), statut VARCHAR(40), libelle_carte VARCHAR(60),
  etape_retenue INT, a_confirmer TINYINT(1), source_statut VARCHAR(255), KEY (zone_id), KEY (statut)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS dalila_cahiers (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id VARCHAR(20), zone VARCHAR(150), annee VARCHAR(10),
  fichier_texte VARCHAR(255), lecture VARCHAR(10), lien_pdf VARCHAR(500), remarque TEXT, KEY (zone_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Registre des sources : chaque page, PDF ou table d'où vient un texte, avec sa date de lecture.
CREATE TABLE IF NOT EXISTS dalila_sources (
  id INT AUTO_INCREMENT PRIMARY KEY, source_url VARCHAR(700), organisme VARCHAR(40), lu_le VARCHAR(20),
  nb_passages INT, UNIQUE KEY (source_url(500))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Passages de texte pour la recherche + leurs vecteurs (remplace ChromaDB).
CREATE TABLE IF NOT EXISTS dalila_passages (
  id VARCHAR(12) PRIMARY KEY, type VARCHAR(40), titre VARCHAR(500), texte MEDIUMTEXT,
  source_url VARCHAR(700), date_source VARCHAR(20), langue VARCHAR(10), zone_id VARCHAR(20) NULL,
  page INT NULL, article VARCHAR(80) NULL, texte_ocr TINYINT(1), kb_id INT NULL, pertinence VARCHAR(20),
  contient_chiffre TINYINT(1), longueur INT,
  embedding_e5 VECTOR(384) NULL, embedding_bge VECTOR(1024) NULL,
  KEY (type), KEY (langue), KEY (zone_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Tables de l'agent (05-data.md §4) : mémoire courte, journal, apprentissage, état des sources.
CREATE TABLE IF NOT EXISTS agent_sessions (session_id VARCHAR(64) PRIMARY KEY, lang VARCHAR(10), slots JSON,
  state VARCHAR(40), updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
CREATE TABLE IF NOT EXISTS agent_turns (id BIGINT AUTO_INCREMENT PRIMARY KEY, session_id VARCHAR(64),
  texte_anonymise TEXT, langue VARCHAR(10), script VARCHAR(10), intention VARCHAR(60), confiance DOUBLE,
  outils JSON, garde_faits VARCHAR(20), latence_ms INT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
CREATE TABLE IF NOT EXISTS agent_needs (id BIGINT AUTO_INCREMENT PRIMARY KEY, texte_anonymise TEXT,
  langue VARCHAR(10), raison VARCHAR(60), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
CREATE TABLE IF NOT EXISTS agent_learning_candidates (id BIGINT AUTO_INCREMENT PRIMARY KEY, kind VARCHAR(40),
  payload JSON, sessions_preuve JSON, status VARCHAR(20), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
CREATE TABLE IF NOT EXISTS agent_learning_journal (id BIGINT AUTO_INCREMENT PRIMARY KEY, candidate_id BIGINT,
  checks JSON, decision VARCHAR(20), graphe_nomme VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  revoked_at TIMESTAMP NULL, revoked_by VARCHAR(80)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
CREATE TABLE IF NOT EXISTS agent_source_status (url VARCHAR(700), last_ok_at TIMESTAMP NULL, last_error TEXT,
  last_error_at TIMESTAMP NULL, content_hash CHAR(64), UNIQUE KEY (url(500)))
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
