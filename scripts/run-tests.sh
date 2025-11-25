#!/bin/bash
set -e

COMPOSE_FILE="docker-compose.test.yml"
SERVICE_APP="app"
SERVICE_DB="db"

echo "Starting services with Docker Compose..."
# Ensure a clean slate by removing any existing containers and volumes
docker compose -f ${COMPOSE_FILE} down --volumes --remove-orphans

TESTING=true docker compose -f ${COMPOSE_FILE} up -d --build

echo "Waiting for the database to be ready..."
# Execute wait-for-db.py in the app container
# The wait-for-db.py script requires DATABASE_URL, which is set in docker-compose.test.yml
docker compose -f ${COMPOSE_FILE} exec -u root ${SERVICE_APP} python /app/scripts/wait-for-db.py

echo "Running tests..."
# Execute pytest in the app container
EXIT_CODE=0
docker compose -f ${COMPOSE_FILE} exec -u root ${SERVICE_APP} poetry run pytest -v "$@" || EXIT_CODE=$?

echo "Cleaning up test resources..."
docker compose -f ${COMPOSE_FILE} down --rmi all --volumes

if [ $EXIT_CODE -ne 0 ]; then
  echo "Tests failed with exit code ${EXIT_CODE}"
  exit ${EXIT_CODE}
else
  echo "Tests completed successfully and resources cleaned up"
fi
