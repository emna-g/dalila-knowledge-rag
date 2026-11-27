-- Vues publiques : la carte ET Dalila lisent les mêmes vues, donc les mêmes chiffres.
-- Elles lisent EN DIRECT les tables de l'AFI (zones, lots, zone_commodites, zone_services, lots_kml) : une mise à
-- jour de l'AFI est visible tout de suite, sans recharger Dalila. Les corrections (dalila_corrections) ne
-- s'appliquent que si la valeur AFI est encore celle d'origine ; sinon la valeur de l'AFI l'emporte.
-- Aucune colonne personnelle (LOT_PROMOTEUR, contrats, dossiers…) n'y apparaît.
-- Les comptes sont calculés ici (COUNT), jamais stockés.
-- Les tables AFI n'ont pas toutes le même interclassement : les identifiants sont ramenés à utf8mb4_general_ci.

CREATE OR REPLACE VIEW v_dalila_corrections_actives AS
SELECT table_afi, cle, champ, valeur_afi, valeur_corrigee, source FROM dalila_corrections WHERE appliquee = 1;

-- Zones AFI, corrections appliquées (toutes les zones ; « visible » = zone_show de l'AFI). Vue interne.
CREATE OR REPLACE VIEW v_dalila_zones AS
SELECT CAST(z.code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci AS zone_id,
       TRIM(IF(c1.cle IS NULL, CONVERT(z.zone_libelle_francais USING utf8mb4) COLLATE utf8mb4_general_ci,
               c1.valeur_corrigee)) AS nom_fr,
       TRIM(IF(c2.cle IS NULL, CONVERT(z.zone_libelle_arabe USING utf8mb4) COLLATE utf8mb4_general_ci,
               c2.valeur_corrigee)) AS nom_ar,
       z.gouv_id AS gouvernorat_code, CAST(z.zone_lat AS DOUBLE) AS lat, CAST(z.zone_long AS DOUBLE) AS lng,
       NULLIF(CAST(IF(c3.cle IS NULL, z.zone_sup_total, c3.valeur_corrigee) AS DOUBLE), 0) AS surface_totale_m2,
       NULLIF(CAST(IF(c4.cle IS NULL, z.zone_sup_amenager, c4.valeur_corrigee) AS DOUBLE), 0) AS surface_amenagee_m2,
       NULLIF(CAST(IF(c5.cle IS NULL, z.prixunitaire, c5.valeur_corrigee) AS DOUBLE), 0) AS prix_m2_dt,
       IF(COALESCE(z.zone_devReg, 0) <> 0, 1, 0) AS zone_developpement_regional,
       IF(z.zone_show = 1, 1, 0) AS visible
FROM zones z
LEFT JOIN v_dalila_corrections_actives c1 ON c1.table_afi = 'zones' AND c1.champ = 'zone_libelle_francais'
     AND c1.cle = z.code_zone AND BINARY c1.valeur_afi = BINARY z.zone_libelle_francais
LEFT JOIN v_dalila_corrections_actives c2 ON c2.table_afi = 'zones' AND c2.champ = 'zone_libelle_arabe'
     AND c2.cle = z.code_zone AND BINARY c2.valeur_afi = BINARY z.zone_libelle_arabe
LEFT JOIN v_dalila_corrections_actives c3 ON c3.table_afi = 'zones' AND c3.champ = 'zone_sup_total'
     AND c3.cle = z.code_zone AND c3.valeur_afi = z.zone_sup_total
LEFT JOIN v_dalila_corrections_actives c4 ON c4.table_afi = 'zones' AND c4.champ = 'zone_sup_amenager'
     AND c4.cle = z.code_zone AND c4.valeur_afi = z.zone_sup_amenager
LEFT JOIN v_dalila_corrections_actives c5 ON c5.table_afi = 'zones' AND c5.champ = 'prixunitaire'
     AND c5.cle = z.code_zone AND c5.valeur_afi = z.prixunitaire;

-- Lots AFI, corrections appliquées (étape et surface). Vue interne.
CREATE OR REPLACE VIEW v_dalila_lots AS
SELECT l.LOT_ID AS lot_id, TRIM(l.ZONE_ID) AS zone_id, TRIM(l.LOT_NUM) AS lot_num,
       CAST(IF(cs.cle IS NULL, l.LOT_SUP_LOTIS, cs.valeur_corrigee) AS SIGNED) AS surface_m2,
       CAST(IF(ce.cle IS NULL, l.LOT_ETAPE, ce.valeur_corrigee) AS SIGNED) AS etape,
       COALESCE(ce.source, 'base AFI afi.sql') AS source_statut, l.LOT_NATURE AS nature
FROM lots l
LEFT JOIN v_dalila_corrections_actives ce ON ce.table_afi = 'lots' AND ce.champ = 'LOT_ETAPE'
     AND ce.cle = l.LOT_ID AND ce.valeur_afi = l.LOT_ETAPE
LEFT JOIN v_dalila_corrections_actives cs ON cs.table_afi = 'lots' AND cs.champ = 'LOT_SUP_LOTIS'
     AND cs.cle = l.LOT_ID AND cs.valeur_afi = l.LOT_SUP_LOTIS;

CREATE OR REPLACE VIEW v_pub_lots AS
SELECT d.lot_id, d.zone_id, z.nom_fr AS zone_fr, d.lot_num, d.surface_m2, e.statut, e.libelle_carte,
       IF(a.lot_id IS NULL, 0, 1) AS a_confirmer, z.prix_m2_dt, d.source_statut,
       IF(z.prix_m2_dt IS NULL, pp.prix_m2_dt, NULL) AS prix_m2_dernier_publie_dt
FROM v_dalila_lots d
JOIN v_dalila_zones z ON z.zone_id = d.zone_id
LEFT JOIN dalila_prix_publies pp ON pp.zone_id = d.zone_id
JOIN dalila_etape_statut e ON e.etape = d.etape
LEFT JOIN dalila_lots_a_confirmer a ON a.lot_id = d.lot_id AND a.etape_afi = d.etape
-- seuls les lots cessibles (LOT_NATURE = 1) : c'est la règle de la carte publique de l'AFI (les autres natures sont
-- des équipements publics, de la voirie… qui ne sont pas à vendre)
WHERE z.visible = 1 AND d.surface_m2 > 0 AND d.nature = 1;

CREATE OR REPLACE VIEW v_pub_lots_disponibles AS SELECT * FROM v_pub_lots WHERE statut = 'disponible';

CREATE OR REPLACE VIEW v_pub_zones AS
SELECT z.zone_id, z.nom_fr, z.nom_ar, g.nom_fr AS gouvernorat_fr, g.nom_ar AS gouvernorat_ar,
       z.gouvernorat_code, z.lat, z.lng, z.surface_totale_m2, z.surface_amenagee_m2, z.prix_m2_dt,
       z.zone_developpement_regional,
       IF(z.zone_developpement_regional = 1, gr.groupe, NULL) AS groupe_developpement_regional,
       IF(z.prix_m2_dt IS NULL, pp.prix_m2_dt, NULL) AS prix_m2_dernier_publie_dt,
       IF(z.prix_m2_dt IS NULL, pp.source, NULL) AS prix_dernier_publie_source,
       IF(z.surface_amenagee_m2 IS NULL, sc.surface_m2, NULL) AS surface_amenagee_calculee_m2,
       ps.prix_m2_dt AS prix_m2_site_afi_dt, ps.prix_m2_subventionne_dt AS prix_m2_subventionne_site_afi_dt,
       ps.source AS prix_site_afi_source,
       IF(ps.prix_m2_dt IS NOT NULL AND z.prix_m2_dt IS NOT NULL AND ps.prix_m2_dt <> z.prix_m2_dt, 1, 0) AS prix_en_conflit,
       CAST(COALESCE(n.disponibles, 0) AS SIGNED) AS lots_disponibles,
       CAST(COALESCE(n.disponibles_a_confirmer, 0) AS SIGNED) AS lots_disponibles_a_confirmer,
       CAST(COALESCE(n.encheres, 0) AS SIGNED) AS lots_mis_aux_encheres
FROM v_dalila_zones z
LEFT JOIN dalila_gouvernorats g ON g.code = z.gouvernorat_code
LEFT JOIN dalila_zone_groupe_dr gr ON gr.zone_id = z.zone_id
LEFT JOIN dalila_prix_publies pp ON pp.zone_id = z.zone_id
LEFT JOIN dalila_zone_surface_contours sc ON sc.zone_id = z.zone_id
LEFT JOIN dalila_prix_site ps ON ps.zone_id = z.zone_id
LEFT JOIN (SELECT zone_id, SUM(statut = 'disponible') AS disponibles,
                  SUM(statut = 'disponible' AND a_confirmer = 1) AS disponibles_a_confirmer,
                  SUM(statut = 'mis_aux_encheres') AS encheres
           FROM v_pub_lots GROUP BY zone_id) n ON n.zone_id = z.zone_id
WHERE z.visible = 1;

-- Distances (com_id 1 à 5) : lignes AFI corrigées + lignes ajoutées par une correction (absentes de la base).
CREATE OR REPLACE VIEW v_pub_zone_distances AS
SELECT d.zone_id, d.type, d.nom, d.km, d.source
FROM (SELECT CAST(k.code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci AS zone_id, t.type,
             TRIM(IF(cn.cle IS NULL, k.zc_libelle_francais COLLATE utf8mb4_general_ci, cn.valeur_corrigee)) AS nom,
             CAST(IF(ck.cle IS NULL, k.zc_distance, ck.valeur_corrigee) AS DOUBLE) AS km,
             COALESCE(ck.source, cn.source, 'base AFI afi.sql') AS source
      FROM zone_commodites k
      JOIN dalila_commodites t ON t.com_id = k.com_id AND t.famille = 'distance'
      LEFT JOIN v_dalila_corrections_actives cn ON cn.table_afi = 'zone_commodites' AND cn.champ = 'zc_libelle_francais'
           AND cn.cle = CONCAT(k.code_zone, ':', k.com_id) AND BINARY cn.valeur_afi = BINARY k.zc_libelle_francais
      LEFT JOIN v_dalila_corrections_actives ck ON ck.table_afi = 'zone_commodites' AND ck.champ = 'zc_distance'
           AND ck.cle = CONCAT(k.code_zone, ':', k.com_id) AND ck.valeur_afi = k.zc_distance
      WHERE k.code_zone <> 0
      UNION ALL
      SELECT SUBSTRING_INDEX(ck.cle, ':', 1), t.type, TRIM(cn.valeur_corrigee), CAST(ck.valeur_corrigee AS DOUBLE),
             ck.source
      FROM v_dalila_corrections_actives ck
      JOIN dalila_commodites t ON t.com_id = SUBSTRING_INDEX(ck.cle, ':', -1) AND t.famille = 'distance'
      LEFT JOIN v_dalila_corrections_actives cn ON cn.table_afi = 'zone_commodites' AND cn.cle = ck.cle
           AND cn.champ = 'zc_libelle_francais'
      WHERE ck.table_afi = 'zone_commodites' AND ck.champ = 'zc_distance' AND ck.valeur_afi IS NULL
        AND NOT EXISTS (SELECT 1 FROM zone_commodites k2 WHERE CONCAT(k2.code_zone, ':', k2.com_id) = ck.cle)) d
JOIN v_dalila_zones z ON z.zone_id = d.zone_id
WHERE z.visible = 1 AND d.km IS NOT NULL
  -- gazoduc nommé par une route (« RN … ») et non corrigé : la valeur n'est pas fiable, on ne la montre pas
  AND NOT (d.type = 'gazoduc' AND d.nom LIKE 'RN%');

-- Équipements (com_id 6 à 11) : valeur de zc_distance avec l'unité ; station d'épuration : « GMG (actif) ».
-- Une valeur 0 veut dire « non renseigné » dans la base AFI (ex. 0 bar de gaz là où le gazoduc passe à 0 km,
-- ou tout à 0 pour El Hancha) : la ligne n'est pas montrée, Dalila répond « information non disponible ».
CREATE OR REPLACE VIEW v_pub_zone_equipements AS
SELECT z.zone_id, t.type,
       IF(t.type = 'station_epuration',
          CONCAT(TRIM(k.zc_libelle_francais), ' (', TRIM(k.zc_unite), ')') COLLATE utf8mb4_general_ci,
          CAST(CAST(k.zc_distance AS DOUBLE) AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci) AS valeur,
       t.unite, 'base AFI afi.sql' AS source
FROM zone_commodites k
JOIN dalila_commodites t ON t.com_id = k.com_id AND t.famille = 'equipement'
JOIN v_dalila_zones z ON z.zone_id = CAST(k.code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci
WHERE z.visible = 1 AND (t.type = 'station_epuration' OR COALESCE(k.zc_distance, 0) > 0);

CREATE OR REPLACE VIEW v_pub_services_proches AS
SELECT z.zone_id, s.categorie, s.nom, s.distance_km, s.lat, s.lng,
       IF(s.source = 'osm', 'OpenStreetMap via base AFI afi.sql', CONCAT(s.source, ' via base AFI afi.sql')) AS source
FROM zone_services s
JOIN v_dalila_zones z ON z.zone_id = CAST(s.code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci
WHERE z.visible = 1;

CREATE OR REPLACE VIEW v_pub_cahiers AS
SELECT zone_id, zone, annee, lien_pdf, remarque FROM dalila_cahiers;

-- Plans de lotissement : lus en direct dans la table AFI zone_documents ; la carte de l'AFI les publie sous /storage/
-- (les 45 plans de la base vérifiés le 2026-11-27). Les cahiers des charges viennent de v_pub_cahiers (liens vérifiés).
CREATE OR REPLACE VIEW v_pub_plans AS
SELECT z.zone_id, d.nom_original AS nom,
       CONCAT('https://carte.afi.nat.tn/storage/', d.fichier) AS lien
FROM zone_documents d
JOIN v_dalila_zones z ON z.zone_id = CAST(d.zone_id AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci
WHERE z.visible = 1 AND d.type = 'plan_lotissement' AND d.fichier IS NOT NULL;

-- Contours des lots (lots_kml) avec leur aire calculée (m², approximation locale, écart < 1 % à cette échelle).
-- Les points KML sont « lng,lat,altitude » ; on garde « lng lat » pour faire un polygone. Vue interne.
CREATE OR REPLACE VIEW v_dalila_contours AS
SELECT g.zone_id, g.lot_num, g.coordonnees,
       ST_Area(g.geo) * POW(111319.49, 2) * COS(RADIANS(ST_Y(ST_Centroid(g.geo)))) AS aire_m2
FROM (SELECT p.zone_id, p.lot_num, p.coordonnees,
             ST_GeomFromText(CONCAT('POLYGON((', p.pts, ',', SUBSTRING_INDEX(p.pts, ',', 1), '))')) AS geo
      FROM (SELECT ZONE_ID AS zone_id, TRIM(LOT_NUM) AS lot_num, LOT_COORDINATES AS coordonnees,
                   REPLACE(REPLACE(TRIM(TRAILING ';' FROM REGEXP_REPLACE(TRIM(LOT_COORDINATES),
                           ',[^,[:space:]]+([[:space:]]+|$)', ';')), ',', ' '), ';', ',') AS pts
            FROM lots_kml) p) g;

-- Un contour n'est montré que si son aire est proche de la surface du lot (entre 2/3 et 1,5 fois) : sinon il dessine
-- autre chose (souvent le lot d'origine, avant découpage). Le lot reste dans la liste, sans dessin.
CREATE OR REPLACE VIEW v_pub_lot_polygones AS
SELECT v.lot_id, v.zone_id, v.lot_num, v.statut, c.coordonnees
FROM v_pub_lots v JOIN v_dalila_contours c ON c.zone_id = v.zone_id AND c.lot_num = v.lot_num
WHERE c.aire_m2 BETWEEN v.surface_m2 / 1.5 AND v.surface_m2 * 1.5;

-- État de chaque correction : appliquee, a_verifier (appliquee = 0) ou perimee (l'AFI a changé la valeur depuis).
-- Pour l'équipe Dalila (non donnée à dalila_ro).
CREATE OR REPLACE VIEW v_dalila_corrections_etat AS
SELECT c.id, c.table_afi, c.cle, c.champ, c.valeur_afi, x.v AS valeur_afi_actuelle, c.valeur_corrigee, c.appliquee,
       CASE WHEN NOT (BINARY c.valeur_afi <=> BINARY x.v) THEN 'perimee'
            WHEN c.appliquee = 1 THEN 'appliquee' ELSE 'a_verifier' END AS etat,
       c.source, c.raison
FROM dalila_corrections c
LEFT JOIN (
  SELECT 'zones' AS t, CAST(code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci AS cle,
         'zone_libelle_francais' AS champ, CONVERT(zone_libelle_francais USING utf8mb4) COLLATE utf8mb4_general_ci AS v
  FROM zones
  UNION ALL SELECT 'zones', CAST(code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'zone_libelle_arabe', CONVERT(zone_libelle_arabe USING utf8mb4) COLLATE utf8mb4_general_ci FROM zones
  UNION ALL SELECT 'zones', CAST(code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'zone_sup_total', CAST(zone_sup_total AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci FROM zones
  UNION ALL SELECT 'zones', CAST(code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'zone_sup_amenager', CAST(zone_sup_amenager AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci FROM zones
  UNION ALL SELECT 'zones', CAST(code_zone AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'prixunitaire', CAST(prixunitaire AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci FROM zones
  UNION ALL SELECT 'lots', CAST(LOT_ID AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'LOT_ETAPE', CAST(LOT_ETAPE AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci FROM lots
  UNION ALL SELECT 'lots', CAST(LOT_ID AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'LOT_SUP_LOTIS', CAST(LOT_SUP_LOTIS AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci FROM lots
  UNION ALL SELECT 'zone_commodites', CAST(CONCAT(code_zone, ':', com_id) AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'zc_distance', CAST(zc_distance AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci FROM zone_commodites
         WHERE code_zone <> 0
  UNION ALL SELECT 'zone_commodites', CAST(CONCAT(code_zone, ':', com_id) AS CHAR CHARACTER SET utf8mb4) COLLATE utf8mb4_general_ci,
         'zc_libelle_francais', CONVERT(zc_libelle_francais USING utf8mb4) COLLATE utf8mb4_general_ci FROM zone_commodites
         WHERE code_zone <> 0
) x ON x.t = c.table_afi AND x.cle = c.cle AND x.champ = c.champ
WHERE c.table_afi <> 'chatbot_connaissances'
UNION ALL
SELECT c.id, c.table_afi, c.cle, c.champ, c.valeur_afi,
       IF(LOCATE(BINARY c.valeur_afi, k.reponse) > 0, c.valeur_afi, NULL), c.valeur_corrigee, c.appliquee,
       CASE WHEN k.id IS NULL OR LOCATE(BINARY c.valeur_afi, k.reponse) = 0 THEN 'perimee'
            WHEN c.appliquee = 1 THEN 'appliquee' ELSE 'a_verifier' END,
       c.source, c.raison
FROM dalila_corrections c
LEFT JOIN chatbot_connaissances k ON k.id = SUBSTRING_INDEX(c.cle, ':', 1)
WHERE c.table_afi = 'chatbot_connaissances';

