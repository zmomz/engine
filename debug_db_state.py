import asyncio
import logging
from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PositionGroup))
        groups = result.scalars().all()
        print(f"Total Position Groups: {len(groups)}")
        for g in groups:
            print(f"ID: {g.id} | Symbol: {g.symbol} | Status: {g.status} | Side: {g.side} | Created: {g.created_at}")

if __name__ == "__main__":
    asyncio.run(check_db())
