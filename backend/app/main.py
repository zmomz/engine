from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import health, webhooks, risk, positions, queue, users
from app.rate_limiter import limiter
from app.services.order_fill_monitor import OrderFillMonitorService
from app.services.take_profit_service import TakeProfitService
from app.services.order_management import OrderService
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.queued_signal import QueuedSignalRepository
from app.db.database import get_db_session, AsyncSessionLocal
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.queue_manager import QueueManagerService
from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.grid_calculator import GridCalculatorService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
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
    # Initialize exchange connector
    app.state.exchange_connector = get_exchange_connector("mock")

    # Initialize repositories and services
    exchange_connector = app.state.exchange_connector

    # Placeholder configurations (will come from user settings in later phases)
    risk_engine_config = RiskEngineConfig()
    dca_grid_config = DCAGridConfig.model_validate([
        {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
    ])
    total_capital_usd = Decimal("10000") # Placeholder

    # OrderFillMonitorService
    app.state.order_fill_monitor = OrderFillMonitorService(
        dca_order_repository_class=DCAOrderRepository,
        order_service_class=OrderService,
        exchange_connector=exchange_connector,
        session_factory=AsyncSessionLocal
    )
    await app.state.order_fill_monitor.start_monitoring()

    # TakeProfitService
    app.state.take_profit_service = TakeProfitService(
        position_group_repository_class=PositionGroupRepository,
        dca_order_repository_class=DCAOrderRepository,
        order_service_class=OrderService,
        exchange_connector=exchange_connector,
        session_factory=AsyncSessionLocal
    )
    await app.state.take_profit_service.start_monitoring()

    # GridCalculatorService
    app.state.grid_calculator_service = GridCalculatorService()

    # ExecutionPoolManager
    app.state.execution_pool_manager = ExecutionPoolManager(
        session_factory=AsyncSessionLocal,
        position_group_repository_class=PositionGroupRepository
    )

    # PositionManagerService
    app.state.position_manager_service = PositionManagerService(
        session_factory=AsyncSessionLocal,
        position_group_repository_class=PositionGroupRepository,
        grid_calculator_service=app.state.grid_calculator_service,
        order_service_class=OrderService
    )

    # QueueManagerService
    app.state.queue_manager_service = QueueManagerService(
        session_factory=AsyncSessionLocal,
        queued_signal_repository_class=QueuedSignalRepository,
        position_group_repository_class=PositionGroupRepository,
        exchange_connector=exchange_connector,
        execution_pool_manager=app.state.execution_pool_manager,
        position_manager_service=app.state.position_manager_service,
        risk_engine_config=risk_engine_config,
        dca_grid_config=dca_grid_config,
        total_capital_usd=total_capital_usd
    )
    await app.state.queue_manager_service.start_promotion_task()

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.order_fill_monitor.stop_monitoring()
    await app.state.take_profit_service.stop_monitoring()
    await app.state.queue_manager_service.stop_promotion_task()


app.include_router(health.router, prefix="/api/health", tags=["Health Check"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk Management"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["Positions"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["Queue"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
