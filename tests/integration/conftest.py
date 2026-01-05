import pytest
import httpx
import os
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.db.database import get_db_session
from app.services.queue_manager import QueueManagerService
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.grid_calculator import GridCalculatorService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from decimal import Decimal
from app.models.user import User
from app.services.order_management import OrderService

from app.services.risk_engine import RiskEngineService
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository

# Add authorized client fixture
from app.core.security import create_access_token
from unittest.mock import patch, MagicMock
from contextlib import asynccontextmanager

# =============================================================================
# Integration Test User Configuration
# =============================================================================
# This dedicated test user is used for integration tests that hit the real
# Docker environment. Using a separate user prevents tests from modifying
# real user data.

# Detect if running in Docker or locally
_IN_DOCKER = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER")
INTEGRATION_BASE_URL = "http://app:8000" if _IN_DOCKER else "http://127.0.0.1:8000"
INTEGRATION_MOCK_URL = "http://mock-exchange:9000" if _IN_DOCKER else "http://127.0.0.1:9000"

# Integration test user credentials - DO NOT use real user accounts
INTEGRATION_TEST_USER = "integration_test_user"
INTEGRATION_TEST_PASSWORD = "integration_test_password_123"
INTEGRATION_TEST_EMAIL = "integration_test@example.com"

# These will be populated after user registration
_integration_user_webhook_id: str = None
_integration_user_webhook_secret: str = None


async def ensure_integration_test_user_exists() -> dict:
    """
    Ensures the integration test user exists in the real database.
    Creates the user if it doesn't exist, or logs in if it does.

    Returns:
        dict with keys: user_id, webhook_id, webhook_secret, access_token
    """
    global _integration_user_webhook_id, _integration_user_webhook_secret

    # Quick health check first (3 second timeout) - fail fast if Docker not running
    try:
        async with httpx.AsyncClient(timeout=3.0) as health_client:
            health_response = await health_client.get(f"{INTEGRATION_BASE_URL}/api/v1/health/")
            if health_response.status_code != 200:
                raise RuntimeError(f"App health check failed: {health_response.status_code}")
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
        raise RuntimeError(f"Docker app not available at {INTEGRATION_BASE_URL}: {e}")

    async with httpx.AsyncClient(timeout=30.0, base_url=INTEGRATION_BASE_URL) as client:
        # First try to login
        login_response = await client.post(
            "/api/v1/users/login",
            data={"username": INTEGRATION_TEST_USER, "password": INTEGRATION_TEST_PASSWORD}
        )

        if login_response.status_code == 200:
            # User exists, get the token
            tokens = login_response.json()
            access_token = tokens["access_token"]

            # Get user profile to retrieve webhook info
            profile_response = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if profile_response.status_code == 200:
                profile = profile_response.json()
                _integration_user_webhook_id = profile.get("id")
                _integration_user_webhook_secret = profile.get("webhook_secret")

                return {
                    "user_id": _integration_user_webhook_id,
                    "webhook_id": _integration_user_webhook_id,
                    "webhook_secret": _integration_user_webhook_secret,
                    "access_token": access_token
                }

        # User doesn't exist, register it
        register_response = await client.post(
            "/api/v1/users/register",
            json={
                "username": INTEGRATION_TEST_USER,
                "email": INTEGRATION_TEST_EMAIL,
                "password": INTEGRATION_TEST_PASSWORD
            }
        )

        if register_response.status_code in (200, 201):
            user_data = register_response.json()
            _integration_user_webhook_id = user_data.get("id")
            _integration_user_webhook_secret = user_data.get("webhook_secret")

            # Login to get access token
            login_response = await client.post(
                "/api/v1/users/login",
                data={"username": INTEGRATION_TEST_USER, "password": INTEGRATION_TEST_PASSWORD}
            )
            tokens = login_response.json()
            access_token = tokens["access_token"]

            # Configure mock exchange API keys for the test user
            await client.post(
                "/api/v1/settings/api-keys",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "exchange": "mock",
                    "api_key": "test_api_key",
                    "secret_key": "test_secret_key"
                }
            )

            return {
                "user_id": _integration_user_webhook_id,
                "webhook_id": _integration_user_webhook_id,
                "webhook_secret": _integration_user_webhook_secret,
                "access_token": access_token
            }

        raise RuntimeError(
            f"Failed to create/login integration test user. "
            f"Login status: {login_response.status_code}, "
            f"Register status: {register_response.status_code}"
        )


def get_integration_test_credentials() -> tuple:
    """
    Returns the integration test user credentials.
    Use this in test files instead of hardcoding credentials.

    Returns:
        tuple: (TEST_USER, TEST_PASSWORD, WEBHOOK_ID, WEBHOOK_SECRET)
    """
    return (
        INTEGRATION_TEST_USER,
        INTEGRATION_TEST_PASSWORD,
        _integration_user_webhook_id,
        _integration_user_webhook_secret
    )


# NOTE: Removed session-scoped event_loop fixture to allow pytest-asyncio
# to create fresh event loops per test, avoiding interference between tests
# that use db_session directly vs HTTP requests to Docker app.
#
# @pytest.fixture(scope="session")
# def event_loop():
#     """Create an instance of the default event loop for the test session."""
#     import asyncio
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


@pytest.fixture(scope="session")
async def integration_test_user_credentials():
    """
    Session-scoped fixture that ensures the integration test user exists
    and returns the credentials for use in tests.

    Usage in tests:
        async def test_something(integration_test_user_credentials):
            creds = integration_test_user_credentials
            webhook_id = creds["webhook_id"]
            webhook_secret = creds["webhook_secret"]
    """
    try:
        credentials = await ensure_integration_test_user_exists()
        return credentials
    except Exception as e:
        pytest.skip(f"Could not setup integration test user: {e}")

class MockEncryptionService:
    """A mock EncryptionService that always returns mock keys to avoid real decryption."""
    def decrypt_keys(self, encrypted_data) -> tuple[str, str]:
        # Always return mock keys for all integration tests to avoid InvalidToken errors
        return "mock_api_key", "mock_secret_key"
    
    def encrypt_keys(self, api_key: str, secret_key: str) -> dict:
        # Return a mock encrypted structure
        return {"encrypted_data": "mock_encrypted_data"}


@pytest.fixture(scope="function")
async def http_client(test_user) -> AsyncClient:
    # Generate a token for the test user
    token = create_access_token(data={"sub": test_user.username})
    headers = {"Authorization": f"Bearer {token}"}
    
    async with AsyncClient(app=app, base_url="http://test", headers=headers) as client:
        yield client

@pytest.fixture(scope="function")
async def override_get_db_session_for_integration_tests(db_session: AsyncSession, test_user: User):
    """Overrides the get_db_session dependency for integration tests and initializes services."""
    app.dependency_overrides = {}
    
    # Patch AsyncSessionLocal used in SignalRouter to use our test db_session
    @asynccontextmanager
    async def mock_session_ctx():
        yield db_session

    mock_factory = MagicMock()
    mock_factory.side_effect = mock_session_ctx
    
    # Apply ALL patches FIRST, then create services inside the patched context
    # Note: Only patch EncryptionService in modules that actually import it
    with patch("app.services.signal_router.AsyncSessionLocal", new=mock_factory):
        with patch("app.core.security.EncryptionService", new=MockEncryptionService):
            with patch("app.services.exchange_abstraction.factory.EncryptionService", new=MockEncryptionService):
                with patch("app.api.settings.EncryptionService", new=MockEncryptionService):
                    # NOW create services INSIDE the patched context
                    mock_exchange_config = {"encrypted_data": "dummy_mock_key"}
                    exchange_connector = get_exchange_connector("mock", mock_exchange_config)
                    risk_engine_config = RiskEngineConfig(
                        loss_threshold_percent=Decimal("-1.5"),
                        required_pyramids_for_timer=3,
                        post_pyramids_wait_minutes=15,
                        max_winners_to_combine=3
                    )
                    dca_grid_config = DCAGridConfig.model_validate({
                        "levels": [
                            {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
                            {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
                            {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
                            {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
                            {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
                        ],
                        "tp_mode": "per_leg",
                        "tp_aggregate_percent": Decimal("0")
                    })
                    total_capital_usd = Decimal("10000")

                    grid_calculator_service = GridCalculatorService()
                    execution_pool_manager = ExecutionPoolManager(
                        session_factory=lambda: db_session,
                        position_group_repository_class=PositionGroupRepository
                    )

                    position_manager_service = PositionManagerService(
                        session_factory=lambda: db_session,
                        user=test_user,
                        position_group_repository_class=PositionGroupRepository,
                        grid_calculator_service=grid_calculator_service,
                        order_service_class=OrderService
                    )

                    risk_engine_service = RiskEngineService(
                        session_factory=lambda: db_session,
                        position_group_repository_class=PositionGroupRepository,
                        risk_action_repository_class=RiskActionRepository,
                        dca_order_repository_class=DCAOrderRepository,
                        order_service_class=OrderService,
                        risk_engine_config=risk_engine_config
                    )

                    app.state.queue_manager_service = QueueManagerService(
                        session_factory=lambda: db_session,
                        user=test_user,
                        queued_signal_repository_class=QueuedSignalRepository,
                        position_group_repository_class=PositionGroupRepository,
                        exchange_connector=exchange_connector,
                        execution_pool_manager=execution_pool_manager,
                        position_manager_service=position_manager_service,
                        polling_interval_seconds=0.01
                    )
                    app.state.exchange_connector = exchange_connector
                    app.state.risk_engine_config = risk_engine_config
                    app.state.dca_grid_config = dca_grid_config

                    # Create proper async generator override for get_db_session
                    async def override_get_db_session():
                        yield db_session

                    app.dependency_overrides[get_db_session] = override_get_db_session

                    yield

    app.dependency_overrides = {}


@pytest.fixture(scope="function")
async def real_services(db_session: AsyncSession, test_user: User):
    """
    Provides real service instances with mock exchange only.
    Tests actual service integration without mocking internal services.

    This fixture is designed to enable integration tests that verify
    actual behavior rather than just mock call verification.

    Usage:
        async def test_something(real_services):
            pm = real_services["position_manager"]
            result = await pm.create_position_group_from_signal(...)

            # Verify actual database state
            repo = PositionGroupRepository(real_services["session"])
            db_position = await repo.get_by_id(result.id)
            assert db_position is not None

    Available services:
        - connector: MockExchangeConnector
        - grid_calculator: GridCalculatorService
        - order_service: OrderService
        - position_manager: PositionManagerService
        - risk_engine: RiskEngineService
        - execution_pool_manager: ExecutionPoolManager
        - session: AsyncSession
        - user: User
    """
    # Patch encryption to avoid real key operations
    with patch("app.services.exchange_abstraction.factory.EncryptionService", new=MockEncryptionService):
        # Create mock exchange connector
        mock_exchange_config = {"encrypted_data": "mock_test_key"}
        connector = get_exchange_connector("mock", mock_exchange_config)

        # Initialize real services with mock exchange
        grid_calculator = GridCalculatorService()

        # Order service needs session, user, and exchange connector
        order_service = OrderService(
            session=db_session,
            user=test_user,
            exchange_connector=connector
        )

        execution_pool_manager = ExecutionPoolManager(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository
        )

        position_manager = PositionManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=grid_calculator,
            order_service_class=OrderService
        )

        risk_engine_config = RiskEngineConfig(
            loss_threshold_percent=Decimal("-1.5"),
            required_pyramids_for_timer=3,
            post_pyramids_wait_minutes=15,
            max_winners_to_combine=3
        )

        risk_engine = RiskEngineService(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository,
            risk_action_repository_class=RiskActionRepository,
            dca_order_repository_class=DCAOrderRepository,
            order_service_class=OrderService,
            risk_engine_config=risk_engine_config
        )

        yield {
            "connector": connector,
            "grid_calculator": grid_calculator,
            "order_service": order_service,
            "position_manager": position_manager,
            "risk_engine": risk_engine,
            "execution_pool_manager": execution_pool_manager,
            "session": db_session,
            "user": test_user,
            "risk_engine_config": risk_engine_config
        }

        # Cleanup
        await connector.close()
