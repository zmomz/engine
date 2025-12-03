import sys
import os
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))

from app.core.config import settings
from app.models.position_group import PositionGroup

# DATABASE_URL is already validated in settings
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5, # Smaller pool for script, adjust as needed
    max_overflow=2,
    echo=False,
)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_active_positions_count(user_id: str):
    async with AsyncSessionLocal() as session:
        stmt = select(PositionGroup).filter(
            PositionGroup.user_id == user_id,
            PositionGroup.status == 'active'
        )
        result = await session.execute(stmt)
        active_positions = result.scalars().all()
        return len(active_positions)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/get_active_positions_count.py <user_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    
    # Initialize settings if not already done (e.g., from .env)
    # This might be redundant if docker-compose exec already sets env vars
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

    count = asyncio.run(get_active_positions_count(user_id))
    print(f'Active positions: {count}/10')
