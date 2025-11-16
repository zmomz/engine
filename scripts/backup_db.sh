#!/bin/bash
set -e

# Load environment variables from .env file
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

DB_CONTAINER="$(docker compose ps -q db)"
DB_NAME="${POSTGRES_DB}"
DB_USER="${POSTGRES_USER}"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

echo "Backing up database '${DB_NAME}' from container '${DB_CONTAINER}' to '${BACKUP_FILE}'..."

docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" > "${BACKUP_FILE}"

echo "Database backup complete: ${BACKUP_FILE}"
