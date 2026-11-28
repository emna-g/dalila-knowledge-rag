#!/bin/sh
# Premier démarrage de MariaDB (volume vide) : charge la base de Dalila déjà construite (donnees/dalila_base.sql.gz :
# tables de l'AFI, textes à citer et leurs vecteurs), sinon afi.sql tel quel (le service préparer calcule le reste).
set -e
if [ -f /donnees/dalila_base.sql.gz ]; then
  echo "chargement de dalila_base.sql.gz"
  zcat /donnees/dalila_base.sql.gz | mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" afi
elif [ -f /donnees/afi.sql ]; then
  echo "chargement de afi.sql"
  mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" afi < /donnees/afi.sql
else
  echo "ni donnees/dalila_base.sql.gz ni donnees/afi.sql : voir docs/docker.md" >&2
  exit 1
fi
