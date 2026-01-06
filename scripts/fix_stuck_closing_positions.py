#!/usr/bin/env python
"""
Fix Stuck Closing Positions

This script finds all positions stuck in "closing" status and reverts them to "active"
so the risk engine can retry the hedge operation.

Usage:
    python scripts/fix_stuck_closing_positions.py
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime

async def fix_stuck_positions():
    """Find and fix positions stuck in 'closing' status."""
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession)() as session:
        # Find all positions in 'closing' status
        result = await session.execute(text("""
            SELECT id, symbol, status, updated_at, total_filled_quantity
            FROM position_groups
            WHERE status = 'closing'
        """))
        rows = result.fetchall()

        if not rows:
            print("No positions found in 'closing' status. Nothing to fix.")
            return

        print(f"Found {len(rows)} position(s) in 'closing' status:")
        for row in rows:
            pos_id, symbol, status, updated_at, qty = row
            time_in_closing = (datetime.utcnow() - updated_at).total_seconds() if updated_at else 0
            print(f"  - {symbol}: id={pos_id}, in_closing_for={time_in_closing:.0f}s, qty={qty}")

        # Ask for confirmation
        confirm = input("\nDo you want to revert these positions to 'active' status? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return

        # Update all closing positions to active
        await session.execute(text("""
            UPDATE position_groups
            SET status = 'active',
                risk_timer_start = NULL,
                risk_timer_expires = NULL,
                risk_eligible = FALSE,
                updated_at = NOW()
            WHERE status = 'closing'
        """))
        await session.commit()

        print(f"\nSuccessfully reverted {len(rows)} position(s) to 'active' status.")
        print("The risk engine will re-evaluate these positions in the next cycle.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_stuck_positions())
