#!/usr/bin/env python3
"""
Set risk timers to expired for testing Risk Engine execution
"""

import asyncio
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/app/backend')

from app.db.database import get_db_session
from app.models.user import User
from app.models.position_group import PositionGroup
from sqlalchemy import select


async def set_timers():
    async for db in get_db_session():
        try:
            result = await db.execute(select(User).where(User.username == 'zmomz'))
            user = result.scalar_one_or_none()

            if not user:
                print("❌ User 'zmomz' not found")
                return

            # Get ADAUSDT (the loser) and set timer to expired
            result = await db.execute(
                select(PositionGroup)
                .where(PositionGroup.user_id == user.id)
                .where(PositionGroup.symbol == 'ADAUSDT')
            )
            ada_pos = result.scalar_one_or_none()

            if ada_pos:
                # Set timer to 1 minute ago (expired)
                ada_pos.risk_timer_expires = datetime.utcnow() - timedelta(minutes=1)
                print(f'Set {ada_pos.symbol} timer to expired: {ada_pos.risk_timer_expires}')
                print(f'  Current PnL: {ada_pos.unrealized_pnl_percent}% (threshold: -0.05%)')
                print(f'  Status: {ada_pos.status}')

            # Get winning positions and set timers
            result = await db.execute(
                select(PositionGroup)
                .where(PositionGroup.user_id == user.id)
                .where(PositionGroup.unrealized_pnl_percent > 0)
            )
            winners = result.scalars().all()

            print(f'\nWinning positions for offset:')
            for pos in winners:
                pos.risk_timer_expires = datetime.utcnow() - timedelta(minutes=1)
                print(f'  {pos.symbol}: {pos.unrealized_pnl_percent}% (${pos.unrealized_pnl_usd})')

            await db.commit()
            print(f'\n✅ Timers set for {len(winners) + 1} positions')

        finally:
            break


async def main():
    await set_timers()


if __name__ == "__main__":
    asyncio.run(main())
