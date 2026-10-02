#!/usr/bin/env bash
# restore.sh - Restore the EchoInsight Postgres database from a gzipped SQL backup.
# Usage: bash scripts/restore.sh <backup_file.sql.gz>
# WARNING: This DROPS and RECREATES the database. All current data will be lost.
set -euo pipefail

BACKUP_FILE="${1:?Usage: bash scripts/restore.sh <backup_file.sql.gz>}"

if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "WARNING: This will DESTROY all current data in the database."
echo "Restoring from: ${BACKUP_FILE}"
read -rp "Type 'yes' to confirm: " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
    PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
    # Extract base URL for dropdb/createdb
    PG_BASE="${PG_URL%/*}"
    PG_DB="${PG_URL##*/}"
    gunzip -c "${BACKUP_FILE}" | psql "${PG_URL}"
else
    PGHOST="${PGHOST:-localhost}"
    PGPORT="${PGPORT:-5432}"
    PGUSER="${PGUSER:-echo}"
    PGDATABASE="${PGDATABASE:-echoinsight}"
    PGPASSWORD="${PGPASSWORD:-}"
    export PGPASSWORD
    gunzip -c "${BACKUP_FILE}" | psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" "${PGDATABASE}"
fi

echo "Restore complete from: ${BACKUP_FILE}"
