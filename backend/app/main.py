from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import health, webhooks, risk, positions, queue, users, settings, dashboard, logs
from app.rate_limiter import limiter
from app.services.order_fill_monitor import OrderFillMonitorService
from app.services.order_management import OrderService
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.risk_action import RiskActionRepository # Added RiskActionRepository import
from app.db.database import get_db_session, AsyncSessionLocal
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.queue_manager import QueueManagerService
from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.grid_calculator import GridCalculatorService
from app.services.risk_engine import RiskEngineService # Added RiskEngineService import
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.models.user import User # Added User import
from app.core.logging_config import setup_logging # Added logging setup
import uuid # Added uuid import
from decimal import Decimal

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)


@app.on_event("startup")
async def startup_event():
    # Setup Logging
    setup_logging()
    
    # Initialize exchange connector
    app.state.exchange_connector = get_exchange_connector("mock")

    # Initialize repositories and services
    exchange_connector = app.state.exchange_connector

    # Create a dummy user for service instantiation (replace with actual user management later)
    async with AsyncSessionLocal() as session:
        # Check if dummy user already exists
        dummy_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001") # Consistent ID
        dummy_user = await session.get(User, dummy_user_id)
        if not dummy_user:
            dummy_user = User(
                id=dummy_user_id,
                username="dummy_system_user",
                email="dummy@example.com",
                hashed_password="dummy_hash", # This will not be used for auth
                exchange="mock",
                webhook_secret="dummy_secret"
            )
            session.add(dummy_user)
            await session.commit()
            await session.refresh(dummy_user)
    app.state.dummy_user = dummy_user

    # OrderFillMonitorService
    app.state.order_fill_monitor = OrderFillMonitorService(
        session_factory=AsyncSessionLocal,
        dca_order_repository_class=DCAOrderRepository,
        position_group_repository_class=PositionGroupRepository,
        exchange_connector=exchange_connector,
        order_service_class=OrderService,
        position_manager_service_class=PositionManagerService
    )
    await app.state.order_fill_monitor.start_monitoring_task()

    # GridCalculatorService is stateless, so it can be initialized at startup
    app.state.grid_calculator_service = GridCalculatorService()

    # RiskEngineConfig and DCAGridConfig (can be loaded from DB/config)
    risk_engine_config = RiskEngineConfig()
    dca_grid_config = DCAGridConfig.model_validate([
        {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
    ])
    total_capital_usd = Decimal("10000") # Placeholder

    # ExecutionPoolManager
    app.state.execution_pool_manager = ExecutionPoolManager(
        session_factory=AsyncSessionLocal,
        position_group_repository_class=PositionGroupRepository
    )

    # PositionManagerService
    app.state.position_manager_service = PositionManagerService(
        session_factory=AsyncSessionLocal,
        user=app.state.dummy_user,
        position_group_repository_class=PositionGroupRepository,
        grid_calculator_service=app.state.grid_calculator_service,
        order_service_class=OrderService,
        exchange_connector=exchange_connector
    )

    # RiskEngineService
    app.state.risk_engine_service = RiskEngineService(
        session_factory=AsyncSessionLocal,
        position_group_repository_class=PositionGroupRepository,
        risk_action_repository_class=RiskActionRepository,
        dca_order_repository_class=DCAOrderRepository,
        exchange_connector=exchange_connector,
        order_service_class=OrderService,
        risk_engine_config=risk_engine_config
    )

    # QueueManagerService
    app.state.queue_manager_service = QueueManagerService(
        session_factory=AsyncSessionLocal,
        user=app.state.dummy_user,
        queued_signal_repository_class=QueuedSignalRepository,
        position_group_repository_class=PositionGroupRepository,
        exchange_connector=exchange_connector,
        execution_pool_manager=app.state.execution_pool_manager,
        position_manager_service=app.state.position_manager_service,
        risk_engine_service=app.state.risk_engine_service,
        grid_calculator_service=app.state.grid_calculator_service,
        order_service_class=OrderService,
        risk_engine_config=risk_engine_config,
        dca_grid_config=dca_grid_config,
        total_capital_usd=total_capital_usd
    )


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.order_fill_monitor.stop_monitoring_task()


app.include_router(health.router, prefix="/api/v1/health", tags=["Health Check"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk Management"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["Positions"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["Queue"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logs"])
