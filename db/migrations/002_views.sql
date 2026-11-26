-- Vues publiques : la carte ET Dalila lisent les mêmes vues, donc les mêmes chiffres.
-- Aucune colonne personnelle (LOT_PROMOTEUR, contrats, dossiers…) n'y apparaît.
-- Les comptes sont calculés ici (COUNT), jamais stockés.

CREATE OR REPLACE VIEW v_pub_lots AS
SELECT l.LOT_ID AS lot_id, s.zone_id, dz.nom_fr AS zone_fr, TRIM(l.LOT_NUM) AS lot_num,
       l.LOT_SUP_LOTIS AS surface_m2, s.statut, s.libelle_carte, s.a_confirmer,
       dz.prix_m2_dt, s.source_statut
FROM lots l
JOIN dalila_lot_statut s ON s.lot_id = l.LOT_ID
JOIN dalila_zones dz ON dz.zone_id = s.zone_id
WHERE dz.visible_dans_la_base = 1 AND s.statut <> 'non_affiche' AND l.LOT_SUP_LOTIS > 0;

CREATE OR REPLACE VIEW v_pub_lots_disponibles AS SELECT * FROM v_pub_lots WHERE statut = 'disponible';

CREATE OR REPLACE VIEW v_pub_zones AS
SELECT dz.zone_id, dz.nom_fr, dz.nom_ar, g.nom_fr AS gouvernorat_fr, g.nom_ar AS gouvernorat_ar,
       dz.gouvernorat_code, dz.lat, dz.lng, dz.surface_totale_m2, dz.surface_amenagee_m2, dz.prix_m2_dt,
       dz.zone_developpement_regional,
       (SELECT COUNT(*) FROM v_pub_lots v WHERE v.zone_id = dz.zone_id AND v.statut = 'disponible') AS lots_disponibles,
       (SELECT COUNT(*) FROM v_pub_lots v WHERE v.zone_id = dz.zone_id AND v.statut = 'disponible'
          AND v.a_confirmer = 1) AS lots_disponibles_a_confirmer,
       (SELECT COUNT(*) FROM v_pub_lots v WHERE v.zone_id = dz.zone_id AND v.statut = 'mis_aux_encheres')
          AS lots_mis_aux_encheres
FROM dalila_zones dz LEFT JOIN dalila_gouvernorats g ON g.code = dz.gouvernorat_code
WHERE dz.visible_dans_la_base = 1;

CREATE OR REPLACE VIEW v_pub_zone_distances AS
SELECT d.zone_id, d.type, d.nom, d.km, d.source FROM dalila_zone_distances d
JOIN dalila_zones dz ON dz.zone_id = d.zone_id WHERE dz.visible_dans_la_base = 1;

CREATE OR REPLACE VIEW v_pub_zone_equipements AS
SELECT e.zone_id, e.type, e.valeur, e.unite, e.source FROM dalila_zone_equipements e
JOIN dalila_zones dz ON dz.zone_id = e.zone_id WHERE dz.visible_dans_la_base = 1;

CREATE OR REPLACE VIEW v_pub_services_proches AS
SELECT s.zone_id, s.categorie, s.nom, s.distance_km, s.lat, s.lng, s.source FROM dalila_services_proches s
JOIN dalila_zones dz ON dz.zone_id = s.zone_id WHERE dz.visible_dans_la_base = 1;

CREATE OR REPLACE VIEW v_pub_cahiers AS
SELECT zone_id, zone, annee, lien_pdf, remarque FROM dalila_cahiers;

CREATE OR REPLACE VIEW v_pub_lot_polygones AS
SELECT v.lot_id, v.zone_id, v.lot_num, v.statut, k.LOT_COORDINATES AS coordonnees
FROM v_pub_lots v JOIN lots_kml k ON TRIM(k.ZONE_ID) = v.zone_id AND TRIM(k.LOT_NUM) = v.lot_num;
