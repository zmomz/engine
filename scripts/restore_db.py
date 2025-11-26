#!/usr/bin/env python3
"""
Restores the PostgreSQL database from a backup file.

Usage:
    python scripts/restore_db.py <backup_file> [--container CONTAINER] [--db-name DB_NAME] [--user DB_USER]
"""
import os
import subprocess
import argparse
import sys
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_env_vars():
    """Simple .env loader"""
    env_vars = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, _, value = line.partition('=')
                    env_vars[key.strip()] = value.strip()
    return env_vars

def main():
    env_vars = load_env_vars()
    
    default_db_name = env_vars.get('POSTGRES_DB', 'execution_engine')
    default_db_user = env_vars.get('POSTGRES_USER', 'postgres')
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backup_file', help='Path to the .sql backup file')
    parser.add_argument('--container', help='Docker container name/ID')
    parser.add_argument('--db-name', default=default_db_name, help=f'Database name (default: {default_db_name})')
    parser.add_argument('--user', default=default_db_user, help=f'Database user (default: {default_db_user})')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()

    if not os.path.exists(args.backup_file):
        logger.error(f"Backup file not found: {args.backup_file}")
        return 1

    # Find container if not provided
    if not args.container:
        try:
            cmd = ["docker", "compose", "ps", "-q", "db"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            args.container = result.stdout.strip()
            if not args.container:
                logger.error("Could not auto-detect DB container. Is docker compose running?")
                return 1
        except subprocess.CalledProcessError:
             logger.error("Failed to execute docker compose ps.")
             return 1

    if not args.no_confirm:
        print(f"WARNING: This will overwrite the database '{args.db_name}' in container '{args.container}'.")
        response = input("Are you sure? (y/N): ")
        if response.lower() != 'y':
            print("Restore cancelled.")
            return 0

    logger.info("Stopping application service...")
    subprocess.run(["docker", "compose", "stop", "app"], check=False)

    try:
        logger.info(f"Recreating database '{args.db_name}'...")
        # Drop and create
        subprocess.run(
            ["docker", "exec", args.container, "dropdb", "-U", args.user, args.db_name, "--if-exists"], 
            check=True
        )
        subprocess.run(
            ["docker", "exec", args.container, "createdb", "-U", args.user, args.db_name],
            check=True
        )

        logger.info(f"Restoring from '{args.backup_file}'...")
        # Restore
        # cat file | docker exec -i ...
        with open(args.backup_file, "r") as f:
            subprocess.run(
                ["docker", "exec", "-i", args.container, "psql", "-U", args.user, "-d", args.db_name],
                stdin=f,
                check=True
            )
        
        logger.info("Restore successful.")

    except subprocess.CalledProcessError as e:
        logger.error(f"Restore failed: {e}")
        return 1
    finally:
        logger.info("Restarting application service...")
        subprocess.run(["docker", "compose", "start", "app"], check=False)
        
        # Apply migrations
        logger.info("Applying migrations...")
        # We might need to wait for app to be ready, but start returns immediately.
        # Ideally we wait-for-db inside the app, but here we just trigger alembic via exec.
        # Since we just started 'app', it might not be ready for exec immediately if it crashes.
        # But 'start' just unpauses/starts the container.
        
        # Let's try to run migrations. If app container isn't running, this fails.
        time.sleep(2) 
        try:
             subprocess.run(
                ["docker", "compose", "exec", "app", "alembic", "upgrade", "head"],
                check=True
             )
             logger.info("Migrations applied.")
        except subprocess.CalledProcessError:
            logger.warning("Could not apply migrations. Check if app container is running.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
