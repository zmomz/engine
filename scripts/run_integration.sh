#!/bin/bash
set -e

# Wait for the database to be ready
# This is a simple loop; a more robust solution might use pg_isready
echo "Waiting for database..."
while ! pg_isready -h db -p 5432 -q -U tv_user; do
  sleep 1
done
echo "Database is ready."

# Upgrade the database to the latest version
echo "Running database migrations..."
poetry run alembic upgrade head

# Run the tests
echo "Running tests..."
exec poetry run pytest --cov=app -v