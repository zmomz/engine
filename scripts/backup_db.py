#!/usr/bin/env python3
"""
Backs up the PostgreSQL database running in a Docker container.

Usage:
    python scripts/backup_db.py [--container CONTAINER] [--db-name DB_NAME] [--user DB_USER] [--output-dir DIR]
"""
import os
import subprocess
import argparse
import datetime
import sys
import logging

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
    parser.add_argument('--container', help='Docker container name/ID')
    parser.add_argument('--db-name', default=default_db_name, help=f'Database name (default: {default_db_name})')
    parser.add_argument('--user', default=default_db_user, help=f'Database user (default: {default_db_user})')
    parser.add_argument('--output-dir', default='./backups', help='Output directory (default: ./backups)')
    
    args = parser.parse_args()

    # Find container if not provided
    if not args.container:
        try:
            # Try to find the db service container from compose
            # Using 'docker compose ps -q db'
            cmd = ["docker", "compose", "ps", "-q", "db"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            args.container = result.stdout.strip()
            if not args.container:
                logger.error("Could not auto-detect DB container. Is docker compose running?")
                return 1
        except subprocess.CalledProcessError:
             logger.error("Failed to execute docker compose ps.")
             return 1

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"db_backup_{timestamp}.sql"
    filepath = os.path.join(args.output_dir, filename)

    logger.info(f"Backing up database '{args.db_name}' from container '{args.container}' to '{filepath}'...")

    # Construct pg_dump command
    # docker exec CONTAINER pg_dump -U USER -d DB > FILE
    dump_cmd = [
        "docker", "exec", args.container,
        "pg_dump", "-U", args.user, "-d", args.db_name
    ]

    try:
        with open(filepath, "w") as f:
            subprocess.run(dump_cmd, stdout=f, check=True)
        logger.info(f"Backup successful: {filepath}")
        return 0
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed: {e}")
        # Cleanup empty file if it exists
        if os.path.exists(filepath) and os.path.getsize(filepath) == 0:
            os.remove(filepath)
        return 1

if __name__ == "__main__":
    sys.exit(main())
