import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# DATABASE_URL is already validated in settings
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=30,           # Increased for high-frequency polling
    max_overflow=20,        # Allow more overflow connections during bursts
    pool_timeout=30,        # Wait up to 30s for a connection
    pool_recycle=1800,      # Recycle connections every 30 minutes
    pool_pre_ping=True,     # Test connections before using them
    echo=False,             # Set to True to see SQL queries
)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
