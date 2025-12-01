import asyncio
import os
import sys
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup, PositionGroupStatus

async def update_ada_active():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "ADAUSDT", PositionGroup.status == "live"))
        ada_group = result.scalars().first()
        if ada_group:
            print(f"Updating ADA {ada_group.id} to ACTIVE")
            ada_group.status = PositionGroupStatus.ACTIVE
            session.add(ada_group)
            await session.commit()
            print("ADA updated.")
        else:
            print("ADA group not found or not live")

if __name__ == "__main__":
    asyncio.run(update_ada_active())
