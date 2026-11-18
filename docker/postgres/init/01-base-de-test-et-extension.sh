#!/bin/bash
# Amorçage de la base IAGORA, joué une seule fois à la création du volume.
#
# Deux bases sont créées :
#   - la base de travail (POSTGRES_DB), que l'image crée elle-même ;
#   - une base de test, vidée à chaque exécution de pytest.
#
# L'extension vectorielle est activée sur les deux : les tests du module 15
# doivent pouvoir tourner, pas seulement le code de travail.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE DATABASE ${POSTGRES_DB}_test OWNER ${POSTGRES_USER};
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${POSTGRES_DB}_test" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "Bases ${POSTGRES_DB} et ${POSTGRES_DB}_test prêtes, extension vector activée."
