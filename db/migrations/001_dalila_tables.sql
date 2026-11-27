-- Tables ajoutées par Dalila À CÔTÉ du schéma de l'AFI (afi.sql est chargé tel quel, sans modification).
-- Règle : un chiffre n'est stocké qu'une fois, dans les tables de l'AFI. Dalila ne garde que ce que l'AFI n'a pas
-- (textes, gouvernorats, cahiers des charges) et ses corrections. Les comptes (lots disponibles par zone…) ne sont
-- PAS stockés : ils sont calculés par les vues (002_views.sql).
-- Même interclassement (collation) que les tables de l AFI (utf8mb4_general_ci), pour pouvoir les joindre.
-- MariaDB 11.8 LTS (type VECTOR). Pour une base 10.11 : remplacer VECTOR(n) par BLOB (recherche numpy).

CREATE TABLE IF NOT EXISTS dalila_gouvernorats (
  code INT PRIMARY KEY, nom_fr VARCHAR(80), nom_ar VARCHAR(80), source VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Zones, lots, distances, équipements et services proches sont lus EN DIRECT dans les tables de l'AFI
-- (zones, lots, zone_commodites, zone_services) par les vues de 002_views.sql. Les anciennes copies sont retirées :
DROP TABLE IF EXISTS dalila_zones, dalila_zone_distances, dalila_zone_equipements, dalila_services_proches,
  dalila_lot_statut;

-- Corrections des valeurs AFI (fichier db/corrections/dalila_corrections.csv, décisions dans DESACCORDS.md).
-- Une correction ne s'applique que si la valeur AFI est encore celle d'origine (valeur_afi) : si l'AFI la change,
-- la correction est « périmée » et la nouvelle valeur de l'AFI est affichée (vue v_dalila_corrections_etat).
-- table_afi / champ : nom de la table et de la colonne AFI ; cle : LOT_ID, code_zone, ou « code_zone:com_id ».
-- Texte de la base de connaissances AFI (chatbot_connaissances) : champ « reponse (extrait) », cle « id:n » ;
-- valeur_afi est un extrait de la réponse, remplacé par valeur_corrigee tant qu'il s'y trouve encore.
CREATE TABLE IF NOT EXISTS dalila_corrections (
  id INT AUTO_INCREMENT PRIMARY KEY, table_afi VARCHAR(40) NOT NULL, cle VARCHAR(40) NOT NULL,
  champ VARCHAR(64) NOT NULL,
  valeur_afi VARCHAR(255) NULL COMMENT 'valeur AFI quand la correction a été écrite ; NULL = ligne absente de la base AFI',
  valeur_corrigee VARCHAR(255) NULL,
  appliquee TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0 = gardée pour mémoire, la valeur AFI est affichée',
  source VARCHAR(255), raison VARCHAR(500),
  UNIQUE KEY (table_afi, cle, champ)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Lots disponibles dans la base mais vus sur aucune carte : signalés « à confirmer » tant que l'étape AFI n'a pas changé.
CREATE TABLE IF NOT EXISTS dalila_lots_a_confirmer (
  lot_id INT PRIMARY KEY, etape_afi INT, raison VARCHAR(255), source VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Autres noms d'une zone (ancienne carte de l'AFI…) : reconnus dans les questions (graphe), jamais affichés.
CREATE TABLE IF NOT EXISTS dalila_zone_alias (
  zone_id VARCHAR(20), alias VARCHAR(150), langue VARCHAR(5), source VARCHAR(255), PRIMARY KEY (zone_id, alias)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Groupe (1 ou 2) des zones de développement régional : la base AFI dit seulement oui / non. Source : carte de la
-- FIPA (décret 2017-389), fichier db/reference/groupes_developpement_regional.csv.
CREATE TABLE IF NOT EXISTS dalila_zone_groupe_dr (
  zone_id VARCHAR(20) PRIMARY KEY, groupe TINYINT, delegation VARCHAR(80), source VARCHAR(500)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Décodage de lots.LOT_ETAPE (libellés lus sur les cartes de l'AFI).
CREATE TABLE IF NOT EXISTS dalila_etape_statut (
  etape INT PRIMARY KEY, statut VARCHAR(40), libelle_carte VARCHAR(60)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
REPLACE INTO dalila_etape_statut VALUES (0, 'sans_statut', '-'), (1, 'disponible', 'Disponible'),
  (2, 'reserve', 'Réservé'), (3, 'attribue', 'Attribué'), (4, 'mis_aux_encheres', 'Mis aux enchères'),
  (5, 'non_disponible', 'Non disponible');

-- Décodage de zone_commodites.com_id : distances (km) et équipements (valeur + unité).
CREATE TABLE IF NOT EXISTS dalila_commodites (
  com_id INT PRIMARY KEY, famille VARCHAR(12), type VARCHAR(40), unite VARCHAR(30)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
REPLACE INTO dalila_commodites VALUES (1, 'distance', 'aeroport', 'km'), (2, 'distance', 'port', 'km'),
  (3, 'distance', 'gare', 'km'), (4, 'distance', 'autoroute', 'km'), (5, 'distance', 'gazoduc', 'km'),
  (6, 'equipement', 'electricite_puissance', 'kVA/ha'), (7, 'equipement', 'eau_debit', 'm3/jour/ha'),
  (8, 'equipement', 'gaz_pression', 'bar'), (10, 'equipement', 'station_epuration', NULL),
  (11, 'equipement', 'telephone', 'paires');

-- Cahiers des charges (db/reference/cahiers.csv) : zone, année, lien du PDF officiel, remarque. Leur texte est dans
-- dalila_passages.
DROP TABLE IF EXISTS dalila_cahiers;
CREATE TABLE dalila_cahiers (
  id INT AUTO_INCREMENT PRIMARY KEY, zone_id VARCHAR(20), zone VARCHAR(150), annee VARCHAR(10),
  lecture VARCHAR(10), lien_pdf VARCHAR(500), remarque TEXT, KEY (zone_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Registre des sources : chaque page, PDF ou table d'où vient un texte, avec sa date de lecture.
CREATE TABLE IF NOT EXISTS dalila_sources (
  id INT AUTO_INCREMENT PRIMARY KEY, source_url VARCHAR(700), organisme VARCHAR(40), lu_le VARCHAR(20),
  nb_passages INT, UNIQUE KEY (source_url(500))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Passages de texte pour la recherche + leurs vecteurs (un modèle par colonne ; recherche dans MariaDB).
CREATE TABLE IF NOT EXISTS dalila_passages (
  id VARCHAR(12) PRIMARY KEY, type VARCHAR(40), titre VARCHAR(500), texte MEDIUMTEXT,
  source_url VARCHAR(700), date_source VARCHAR(20), langue VARCHAR(10), zone_id VARCHAR(20) NULL,
  page INT NULL, article VARCHAR(80) NULL, texte_ocr TINYINT(1), kb_id INT NULL, pertinence VARCHAR(20),
  contient_chiffre TINYINT(1), longueur INT,
  embedding_e5 VECTOR(384) NULL, embedding_bge VECTOR(1024) NULL, embedding_qwen VECTOR(1024) NULL,
  KEY (type), KEY (langue), KEY (zone_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Base créée avant l'ajout du modèle Qwen3 : on ajoute sa colonne.
ALTER TABLE dalila_passages ADD COLUMN IF NOT EXISTS embedding_qwen VECTOR(1024) NULL;

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
