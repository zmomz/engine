import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio
import os

from app.db.database import get_db_session
from app.models.base import Base
from app.main import app
from httpx import AsyncClient
from app.models.user import User
from app.core.security import SECRET_KEY, ALGORITHM, get_password_hash

POSTGRES_USER = os.environ.get("POSTGRES_USER", "tv_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "tv_engine_db_test")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@db:5432/tv_engine_db_test"
)
TEST_PASSWORD = "testpassword"

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession, test_user: User):
    async def _get_test_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = _get_test_db_session
    
    # Disable rate limiter for tests
    app.state.limiter.enabled = False
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    # Re-enable rate limiter
    app.state.limiter.enabled = True
    
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
    hashed_pwd = get_password_hash(TEST_PASSWORD)
    user = User(
        username="testuser", 
        email="test@example.com", 
        hashed_password=hashed_pwd, 
        exchange="binance", 
        webhook_secret="secret", 
        is_active=True,
        encrypted_api_keys={"encrypted_data": "dummy_encrypted_key"},
        dca_grid_config=[
            {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
            {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
        ]
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
async def authorized_client(client: AsyncClient, test_user: User):
    # Login the user to get a token using the plain password
    login_data = {"username": "testuser", "password": TEST_PASSWORD} 
    response = await client.post(
        "/api/v1/users/login",
        data=login_data
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    tokens = response.json()
    access_token = tokens["access_token"]

    # Return a new client with the authorization header
    async with AsyncClient(app=app, base_url="http://test", headers={
        "Authorization": f"Bearer {access_token}"
    }) as auth_client:
        yield auth_client

@pytest.fixture(scope="function", autouse=True)
def mock_encryption():
    with patch("app.core.security.EncryptionService.decrypt_keys", return_value=("mock_api_key", "mock_secret_key")):
        yield


@pytest.fixture
def mock_async_session():
    """Provides a mock SQLAlchemy AsyncSession."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = AsyncMock()
    mock_session.execute.return_value = mock_result
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    return mock_session