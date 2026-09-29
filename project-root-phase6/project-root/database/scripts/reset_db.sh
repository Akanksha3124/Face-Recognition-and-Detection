#!/usr/bin/env bash
# Convenience script for local dev: drops and recreates the database,
# reapplies all migrations, then seeds demo data.
set -euo pipefail

DB_NAME="${DB_NAME:-person_id_platform}"
DB_USER="${DB_USER:-postgres}"

psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
psql -U "$DB_USER" -c "CREATE DATABASE ${DB_NAME};"

cd "$(dirname "$0")/../../backend"
alembic upgrade head

cd ..
python -m database.seeds.seed
