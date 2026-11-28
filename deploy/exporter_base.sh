#!/bin/sh
# Exporte la base construite dans donnees/dalila_base.sql.gz (chargée au premier démarrage du service db, docs/docker.md).
# Sans les conversations ni l'apprentissage (tables agent_*, recréées vides par migrer) ni les vues (recréées par migrer).
#   sh deploy/exporter_base.sh               depuis le service db de docker compose
#   sh deploy/exporter_base.sh afi_cmp       depuis un autre conteneur MariaDB
set -e
cd "$(dirname "$0")/.."
PW=$(grep '^DB_ROOT_PASSWORD=' .env | cut -d= -f2-)
if [ -n "$1" ]; then EXEC="docker exec -i -e MYSQL_PWD=$PW $1"; else EXEC="docker compose exec -T -e MYSQL_PWD=$PW db"; fi
IGN=$($EXEC mariadb -uroot -N afi -e "SELECT CONCAT('--ignore-table=afi.', table_name) FROM information_schema.tables
  WHERE table_schema = 'afi' AND (table_type = 'VIEW' OR table_name LIKE 'agent\_%')" | tr '\n' ' ')
$EXEC sh -c "mariadb-dump -uroot --single-transaction --default-character-set=utf8mb4 --hex-blob $IGN afi | gzip -9" \
  > donnees/dalila_base.sql.gz.new
mv donnees/dalila_base.sql.gz.new donnees/dalila_base.sql.gz
ls -l donnees/dalila_base.sql.gz
