import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

from app.db.database import get_db_session
from app.models.base import Base
from app.main import app
from httpx import AsyncClient
from app.models.user import User

DATABASE_URL = "postgresql+asyncpg://tv_user:your_password@db:5432/tv_engine_db_test"

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def _get_test_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _get_test_db_session
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def test_db_engine():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(test_db_engine):
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        await session.begin_nested()
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession):
    user = User(username="testuser", email="test@example.com", hashed_password="hashedpassword", exchange="binance")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user



@pytest.fixture
def mock_async_session():
    """Provides a mock SQLAlchemy AsyncSession."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    return mock_session