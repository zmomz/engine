import pytest
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
from app.core.security import EncryptionService as RealEncryptionService # Rename original for use in mock

class MockEncryptionService:
    """A mock EncryptionService that can return specific mock keys for 'dummy_mock_key'."""
    def decrypt_keys(self, encrypted_data: dict) -> tuple[str, str]:
        if "dummy_mock_key" in str(encrypted_data):
            return "mock_api_key", "mock_secret_key"
        # For non-mock encrypted_data, attempt to use the real decryption logic
        return RealEncryptionService().decrypt_keys(encrypted_data)


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
    
    # Initialize services and attach to app.state for integration tests
    exchange_connector = get_exchange_connector("mock")
    risk_engine_config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-1.5"),
        timer_start_condition="after_all_dca_filled",
        post_full_wait_minutes=15,
        max_winners_to_combine=3
    )
    dca_grid_config = DCAGridConfig.model_validate([
        {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
    ])
    total_capital_usd = Decimal("10000")

    grid_calculator_service = GridCalculatorService()
    execution_pool_manager = ExecutionPoolManager(
        session_factory=lambda: db_session,
        position_group_repository_class=PositionGroupRepository
    )

    # Debug print
    print(f"DEBUG: PositionManagerService is {PositionManagerService}")
    
    position_manager_service = PositionManagerService(
        session_factory=lambda: db_session,
        user=test_user,
        position_group_repository_class=PositionGroupRepository,
        grid_calculator_service=grid_calculator_service,
        order_service_class=OrderService,
        exchange_connector=exchange_connector
    )
    
    risk_engine_service = RiskEngineService(
        session_factory=lambda: db_session,
        position_group_repository_class=PositionGroupRepository,
        risk_action_repository_class=RiskActionRepository,
        dca_order_repository_class=DCAOrderRepository,
        exchange_connector=exchange_connector,
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

    app.dependency_overrides[get_db_session] = lambda: db_session
    
    # Patch AsyncSessionLocal used in SignalRouter to use our test db_session
    @asynccontextmanager
    async def mock_session_ctx():
        yield db_session

    mock_factory = MagicMock()
    mock_factory.side_effect = mock_session_ctx
    
    with patch("app.services.signal_router.AsyncSessionLocal", new=mock_factory):
        with patch("app.core.security.EncryptionService", new=MockEncryptionService):
            with patch("app.api.risk.EncryptionService", new=MockEncryptionService):
                yield
        
    app.dependency_overrides = {}
