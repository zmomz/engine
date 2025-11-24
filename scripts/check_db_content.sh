#!/bin/bash
set -e

# Load environment variables from .env file
if [ -f .env ]; then
  # export $(cat .env | xargs) # Use a safer method if values have spaces, but this matches existing scripts
  export $(grep -v '^#' .env | grep -vE '^(UID|GID)=' | xargs)
fi

DB_SERVICE="db"
DB_NAME="${POSTGRES_DB}"
DB_USER="${POSTGRES_USER}"

# Check if DB variables are set
if [ -z "$DB_NAME" ] || [ -z "$DB_USER" ]; then
    echo "Error: POSTGRES_DB or POSTGRES_USER not set in .env"
    exit 1
fi

echo "Checking content of database '$DB_NAME' in service '$DB_SERVICE'வைக்"

# Get list of tables (public schema only)
echo "Fetching table list from database '$DB_NAME'..."
set +e
TABLES=$(docker compose exec -T $DB_SERVICE psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null)
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo "Warning: Could not connect to database '$DB_NAME'. Checking for other databases..."
    EXISTING_DBS=$(docker compose exec -T $DB_SERVICE psql -U "$DB_USER" -d template1 -t -A -c "SELECT datname FROM pg_database WHERE datistemplate = false;" 2>/dev/null)
    
    # Check if a likely alternative exists (e.g., tv_engine_db)
    if echo "$EXISTING_DBS" | grep -q "tv_engine_db"; then
        echo "Found existing database 'tv_engine_db'. Switching to it."
        DB_NAME="tv_engine_db"
        TABLES=$(docker compose exec -T $DB_SERVICE psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
    else
        echo "Error: Configured database '$DB_NAME' not found and no obvious alternative detected."
        echo "Available databases:"
        echo "$EXISTING_DBS"
        exit 1
    fi
fi

if [ -z "$TABLES" ]; then
    echo "No tables found in the database (public schema)."
    exit 0
fi

echo "Found the following tables:"
echo "$TABLES" | tr ' ' '\n'
echo "==================================================="

# Loop through tables and print content
for TABLE in $TABLES; do
    echo "TABLE: $TABLE (First 20 rows)"
    echo "---------------------------------------------------"
    docker compose exec -T $DB_SERVICE psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT * FROM \"$TABLE\" LIMIT 20;"
    echo "==================================================="
    echo ""
done

echo "Check complete."
