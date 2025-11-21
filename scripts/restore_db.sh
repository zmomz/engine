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

# Check if a backup file is provided as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <backup_file>"
  echo "Available backups:"
  ls -lh "${BACKUP_DIR}"/*.sql 2>/dev/null || echo "  No backups found."
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "Error: Backup file '${BACKUP_FILE}' not found!"
  exit 1
fi

echo "Restoring database '${DB_NAME}' in container '${DB_CONTAINER}' from '${BACKUP_FILE}'..."

# Stop the application service to prevent connections during restore
echo "Stopping app service..."
docker compose stop app

# Drop existing database and recreate it
docker exec "${DB_CONTAINER}" dropdb -U "${DB_USER}" "${DB_NAME}" || true
docker exec "${DB_CONTAINER}" createdb -U "${DB_USER}" "${DB_NAME}"

# Restore the database from the backup file
docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" < "${BACKUP_FILE}"

# Start the application service again
echo "Starting app service..."
docker compose start app

# Apply Alembic migrations to ensure schema is up-to-date after restore
# We must wait for the app container to be ready or just use 'run' if exec fails, 
# but since we just started it, exec should work once it's up.
echo "Applying Alembic migrations after restore..."
docker compose exec app alembic upgrade head

echo "Database restore complete from ${BACKUP_FILE}"
