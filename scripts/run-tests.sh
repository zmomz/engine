#!/bin/bash
set -e

echo "Running tests..."
TESTING=true docker compose -f docker-compose.test.yml run --rm --build app poetry run pytest -v "$@"

echo "Cleaning up test resources..."
docker compose -f docker-compose.test.yml down --rmi all --volumes

echo "Tests completed and resources cleaned up"
