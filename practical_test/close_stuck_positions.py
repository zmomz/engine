import asyncio
import os
import sys
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup, PositionGroupStatus

async def close_stuck_positions():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PositionGroup).where(PositionGroup.status == "live"))
        groups = result.scalars().all()
        for g in groups:
            print(f"Closing group {g.id} ({g.symbol} {g.exchange})")
            g.status = PositionGroupStatus.CLOSED
            session.add(g)
        await session.commit()
        print("Stuck positions closed.")

if __name__ == "__main__":
    asyncio.run(close_stuck_positions())
