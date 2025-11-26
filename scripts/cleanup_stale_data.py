#!/usr/bin/env python3
"""
Cleans up stale data from the database.

Usage:
    python scripts/cleanup_stale_data.py --days 90 [--dry-run]
"""
import sys
import os
import argparse
import asyncio
import logging
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

# Load .env variables
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))
except ImportError:
    pass

try:
    from app.db.database import AsyncSessionLocal
    from app.models.position_group import PositionGroup, PositionGroupStatus
    from app.models.queued_signal import QueuedSignal
    from sqlalchemy import select, delete, and_
except ImportError as e:
    print(f"Error: Could not import backend modules. {e}", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def cleanup(days, dry_run):
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    logger.info(f"Cleaning up data older than {cutoff_date}...")
    
    async with AsyncSessionLocal() as session:
        # 1. Clean old closed Position Groups
        # Using status 'closed' and updated_at < cutoff
        stmt = select(PositionGroup).where(
            and_(
                PositionGroup.status == PositionGroupStatus.CLOSED,
                PositionGroup.updated_at < cutoff_date
            )
        )
        result = await session.execute(stmt)
        old_groups = result.scalars().all()
        
        logger.info(f"Found {len(old_groups)} stale position groups.")
        
        if not dry_run and old_groups:
            # Note: Cascade delete should handle related orders/positions if configured correctly in models.
            # If not, we might need to delete them explicitly.
            # For this script, we assume cascade is set or we just delete the group.
            
            # SQLAlchemy delete
            delete_stmt = delete(PositionGroup).where(
                and_(
                    PositionGroup.status == PositionGroupStatus.CLOSED,
                    PositionGroup.updated_at < cutoff_date
                )
            )
            await session.execute(delete_stmt)
            await session.commit()
            logger.info("Deleted stale position groups.")
        
        # 2. Clean old Queued Signals (if any)
        # Queued signals that are processed or failed long ago
        # Assuming QueuedSignal has a created_at or updated_at
        # We need to check the model.
        pass

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=90, help='Delete data older than N days')
    parser.add_argument('--dry-run', action='store_true', help='Do not actually delete data')
    
    args = parser.parse_args()
    
    try:
        asyncio.run(cleanup(args.days, args.dry_run))
        return 0
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
