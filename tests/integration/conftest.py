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

@pytest.fixture(scope="function")
async def http_client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture(scope="function", autouse=True)
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
        session=db_session,
        position_group_repository_class=PositionGroupRepository
    )
    position_manager_service = PositionManagerService(
        session=db_session,
        user=test_user,
        position_group_repository_class=PositionGroupRepository,
        grid_calculator_service=grid_calculator_service,
        order_service_class=OrderService,
        exchange_connector=exchange_connector
    )
    
    app.state.queue_manager_service = QueueManagerService(
        session=db_session,
        user=test_user,
        queued_signal_repository_class=QueuedSignalRepository,
        position_group_repository_class=PositionGroupRepository,
        exchange_connector=exchange_connector,
        execution_pool_manager=execution_pool_manager,
        position_manager_service=PositionManagerService,
        grid_calculator_service=grid_calculator_service,
        order_service_class=OrderService,
        risk_engine_config=risk_engine_config,
        dca_grid_config=dca_grid_config,
        total_capital_usd=total_capital_usd
    )
    app.state.exchange_connector = exchange_connector
    app.state.risk_engine_config = risk_engine_config
    app.state.dca_grid_config = dca_grid_config

    app.dependency_overrides[get_db_session] = lambda: db_session
    yield
    app.dependency_overrides = {}
