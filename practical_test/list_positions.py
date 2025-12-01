import asyncio
import os
import sys
from sqlalchemy import select, func

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup

async def list_positions():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PositionGroup))
        groups = result.scalars().all()
        print(f"Total Positions: {len(groups)}")
        for g in groups:
            print(f"ID: {g.id} Symbol: {g.symbol} Status: {g.status} User ID: {g.user_id}")

if __name__ == "__main__":
    asyncio.run(list_positions())
