import asyncio
import os
import sys

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup
from app.models.user import User
from sqlalchemy import select, func

async def get_active_positions():
    async with AsyncSessionLocal() as session:
        count_query = select(func.count(PositionGroup.id)).where(
            PositionGroup.user_id == 'c788bbcd-57e7-42f7-aa06-870a8dfc994f',
            PositionGroup.status == 'active'
        )
        result = await session.execute(count_query)
        active_count = result.scalar_one()
        print(f"Active positions: {active_count}/10")

if __name__ == "__main__":
    asyncio.run(get_active_positions())