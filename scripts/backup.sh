#!/usr/bin/env bash
# backup.sh - Dump the EchoInsight Postgres database to a timestamped gzipped SQL file.
# Usage: bash scripts/backup.sh [output_dir]
# Requires: pg_dump, gzip, POSTGRES_* environment variables or DATABASE_URL.
set -euo pipefail

OUTPUT_DIR="${1:-backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="echoinsight_${TIMESTAMP}.sql.gz"
OUTPUT_PATH="${OUTPUT_DIR}/${FILENAME}"

mkdir -p "${OUTPUT_DIR}"

# Parse from DATABASE_URL if set; otherwise expect individual PG vars.
if [[ -n "${DATABASE_URL:-}" ]]; then
    # Strip driver prefix (postgresql+asyncpg:// -> postgresql://)
    PG_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"
    pg_dump "${PG_URL}" | gzip > "${OUTPUT_PATH}"
else
    PGHOST="${PGHOST:-localhost}"
    PGPORT="${PGPORT:-5432}"
    PGUSER="${PGUSER:-echo}"
    PGDATABASE="${PGDATABASE:-echoinsight}"
    PGPASSWORD="${PGPASSWORD:-}"
    export PGPASSWORD
    pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" "${PGDATABASE}" | gzip > "${OUTPUT_PATH}"
fi

echo "Backup written to: ${OUTPUT_PATH}"
echo "Size: $(du -sh ${OUTPUT_PATH} | cut -f1)"
