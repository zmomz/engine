import asyncio
import os
import sys
from sqlalchemy import select, func

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup, PositionGroupStatus

async def count_positions():
    async with AsyncSessionLocal() as session:
        active_statuses = ["live", "partially_filled", "active", "closing"]
        
        # List all
        result = await session.execute(select(PositionGroup))
        groups = result.scalars().all()
        print("All Groups:")
        for g in groups:
            print(f"  {g.id} {g.symbol} {g.status}")
            
        # Count
        query = select(func.count(PositionGroup.id)).where(PositionGroup.status.in_(active_statuses))
        result = await session.execute(query)
        count = result.scalar_one()
        print(f"Count Active: {count}")

if __name__ == "__main__":
    asyncio.run(count_positions())
