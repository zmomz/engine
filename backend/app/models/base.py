from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


# Async engine and session setup (example, adjust as needed)
# This will be properly configured in the main application setup
# For alembic, we only need the Base.metadata
async_engine = None
AsyncSessionLocal = None

def configure_db(database_url: str):
    global async_engine, AsyncSessionLocal
    async_engine = create_async_engine(database_url)
    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)
