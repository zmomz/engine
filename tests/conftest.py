import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio
import os
import uuid
from unittest import mock # Import the whole module

from app.db.database import get_db_session
from app.models.base import Base
from app.main import app
from httpx import AsyncClient
from app.models.user import User
from app.core.security import SECRET_KEY, ALGORITHM, get_password_hash, EncryptionService
from decimal import Decimal

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
    # SAFETY CHECK: Prevent running tests against non-test databases
    if "test" not in DATABASE_URL and "test" not in POSTGRES_DB:
        raise pytest.UsageError(
            f"CRITICAL: Attempting to run tests against a non-test database ({DATABASE_URL}). "
            "Tests perform destructive actions (DROP ALL TABLES). "
            "Please set DATABASE_URL to a test database (e.g., ending in '_test')."
        )

    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        from sqlalchemy import text
        try:
            await conn.execute(text("CREATE TYPE group_status_enum AS ENUM ('waiting', 'live', 'partially_filled', 'active', 'closing', 'closed', 'failed')"))
            await conn.execute(text("CREATE TYPE position_side_enum AS ENUM ('long', 'short')"))
            await conn.execute(text("CREATE TYPE tp_mode_enum AS ENUM ('per_leg', 'aggregate', 'hybrid')"))
        except Exception:
            pass # Type might already exist
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
        yield session
        await session.close() # Ensure the session is closed after the test


@pytest.fixture(scope="function")
async def create_user_with_configs(db_session: AsyncSession):
    """
    Factory fixture to create a User object with consistently formatted
    risk_config and dca_grid_config, converting Decimals to strings for JSON serialization.
    """
    # Helper to convert Decimal to str for JSON serialization
    def convert_decimals_to_str(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert_decimals_to_str(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_decimals_to_str(elem) for elem in obj]
        return obj

    async def _factory(username: str = "testuser", email: str = "test@example.com", 
                       exchange: str = "binance", webhook_secret: str = "secret") -> User:
        hashed_pwd = get_password_hash(TEST_PASSWORD)
        
        # Generate valid encrypted keys
        encryption_service = EncryptionService()
        valid_encrypted_keys = {
            "binance": encryption_service.encrypt_keys("dummy_api", "dummy_secret"),
            "mock": encryption_service.encrypt_keys("dummy_mock_api", "dummy_mock_secret")
        }
        
        # Use the actual config schemas and then convert to JSON serializable dict
        from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

        risk_config_data = RiskEngineConfig().model_dump()
        dca_grid_config_data = DCAGridConfig(
            levels=[
                {"gap_percent": Decimal("0.0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("1.0")},
                {"gap_percent": Decimal("-0.5"), "weight_percent": Decimal("20"), "tp_percent": Decimal("0.5")},
                {"gap_percent": Decimal("-1.0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("0.5")},
                {"gap_percent": Decimal("-2.0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("0.5")},
                {"gap_percent": Decimal("-4.0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("0.5")}
            ],
            tp_mode="per_leg",
            tp_aggregate_percent=Decimal("0")
        ).model_dump()

        user = User(
            id=uuid.uuid4(),
            username=username, 
            email=email, 
            hashed_password=hashed_pwd, 
            exchange=exchange, 
            webhook_secret=webhook_secret, 
            is_active=True,
            encrypted_api_keys=valid_encrypted_keys,
            risk_config=convert_decimals_to_str(risk_config_data),
            dca_grid_config=convert_decimals_to_str(dca_grid_config_data)
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    
    return _factory

@pytest.fixture(scope="function")
async def test_user(create_user_with_configs):
    return await create_user_with_configs()

@pytest.fixture(scope="function")
async def authorized_client(client: AsyncClient, test_user: User):
    # Login the user to get a token using the plain password
    login_data = {"username": test_user.username, "password": TEST_PASSWORD} 
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



@pytest.fixture
def mock_async_session():
    """Provides a mock SQLAlchemy AsyncSession."""
    mock_session = mock.AsyncMock(spec=AsyncSession)
    mock_result = mock.AsyncMock()
    
    # Mock for result.scalars()
    mock_scalars_result = mock.MagicMock()
    mock_scalars_result.all.return_value = []
    mock_scalars_result.first.return_value = None
    
    # When mock_result.scalars() is called, it should return mock_scalars_result directly
    mock_result.scalars.return_value = mock_scalars_result
    
    # When mock_session.execute is called, it should return an object that can be awaited
    # and then used to call .scalars()
    mock_execute_return_value = mock.AsyncMock()
    mock_execute_return_value.scalars.return_value = mock_scalars_result
    mock_session.execute.return_value = mock_execute_return_value
    
    # Also mock session.get for specific calls if needed, as it bypasses execute/scalars
    mock_session.get.return_value = None # Default, can be overridden per test
    mock_session.commit = mock.AsyncMock() # Ensure commit is awaitable
    mock_session.refresh = mock.AsyncMock() # Ensure refresh is awaitable
    mock_session.close = mock.AsyncMock() # Ensure close is awaitable
    mock_session.rollback = mock.AsyncMock() # Ensure rollback is awaitable

    return mock_session