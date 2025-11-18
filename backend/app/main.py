from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import health, webhooks, risk, positions, queue, users, settings
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

    # OrderFillMonitorService
    app.state.order_fill_monitor = OrderFillMonitorService(
        dca_order_repository_class=DCAOrderRepository,
        user_repository_class=UserRepository,
        order_service_class=OrderService,
        exchange_connector=exchange_connector,
        session_factory=AsyncSessionLocal
    )
    await app.state.order_fill_monitor.start_monitoring()

    # TakeProfitService
    app.state.take_profit_service = TakeProfitService(
        position_group_repository_class=PositionGroupRepository,
        dca_order_repository_class=DCAOrderRepository,
        user_repository_class=UserRepository,
        order_service_class=OrderService,
        exchange_connector=exchange_connector,
        session_factory=AsyncSessionLocal
    )
    await app.state.take_profit_service.start_monitoring()

    # GridCalculatorService is stateless, so it can be initialized at startup
    app.state.grid_calculator_service = GridCalculatorService()


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.order_fill_monitor.stop_monitoring()
    await app.state.take_profit_service.stop_monitoring()


app.include_router(health.router, prefix="/api/v1/health", tags=["Health Check"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk Management"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["Positions"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["Queue"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])
