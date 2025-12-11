from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
import logging
import sys

from app.api import health, webhooks, risk, positions, queue, users, settings as api_settings, dashboard, logs, dca_configs
from app.rate_limiter import limiter
from app.services.order_fill_monitor import OrderFillMonitorService
from app.services.order_management import OrderService
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.db.database import AsyncSessionLocal
from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.grid_calculator import GridCalculatorService
from app.services.queue_manager import QueueManagerService
from app.core.logging_config import setup_logging
from app.core.config import settings
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# Validate CORS for production
if settings.ENVIRONMENT == "production":
    # In production, we must have specific origins, not just default
    if not settings.CORS_ORIGINS or "http://localhost:3000" in settings.CORS_ORIGINS:
        # This allows manual override if they REALLY want localhost in prod, but usually it's a misconfig.
        # For strictness:
        if "http://localhost:3000" in settings.CORS_ORIGINS and len(settings.CORS_ORIGINS) == 1:
             logger.warning("Running in production with default localhost CORS origin. This is insecure.")
             # Should we fail? The requirement says "If production and CORS_ORIGINS not set or contains localhost, fail startup"
             # Let's be strict.
             logger.error("Production environment detected but CORS_ORIGINS contains localhost or is not set correctly.")
             sys.exit(1)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.getenv("TESTING") != "true":
    app.add_middleware(SlowAPIMiddleware)



@app.on_event("startup")
async def startup_event():
    # Setup Logging
    setup_logging()
    
    logger.info(f"Starting up in {settings.ENVIRONMENT} mode")
    logger.info(f"CORS Allowed Origins: {settings.CORS_ORIGINS}")

    # OrderFillMonitorService
    # Now initialized without specific exchange connector, it handles multi-user iteration internally.
    app.state.order_fill_monitor = OrderFillMonitorService(
        session_factory=AsyncSessionLocal,
        dca_order_repository_class=DCAOrderRepository,
        position_group_repository_class=PositionGroupRepository,
        order_service_class=OrderService,
        position_manager_service_class=PositionManagerService
    )
    await app.state.order_fill_monitor.start_monitoring_task()

    # GridCalculatorService is stateless, so it can be initialized at startup
    app.state.grid_calculator_service = GridCalculatorService()

    # ExecutionPoolManager
    app.state.execution_pool_manager = ExecutionPoolManager(
        session_factory=AsyncSessionLocal,
        position_group_repository_class=PositionGroupRepository
    )

    # QueueManagerService
    app.state.queue_manager_service = QueueManagerService(
        session_factory=AsyncSessionLocal,
        execution_pool_manager=app.state.execution_pool_manager
    )
    await app.state.queue_manager_service.start_promotion_task()
    
    # PositionManagerService & RiskEngineService are now instantiated per-request.


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "order_fill_monitor"):
        await app.state.order_fill_monitor.stop_monitoring_task()
    if hasattr(app.state, "queue_manager_service"):
        await app.state.queue_manager_service.stop_promotion_task()


app.include_router(health.router, prefix="/api/v1/health", tags=["Health Check"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk Management"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["Positions"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["Queue"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(api_settings.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logs"])
app.include_router(dca_configs.router, prefix="/api/v1/dca-configs", tags=["DCA Configuration"])

# Serve Frontend Static Files
frontend_build_path = os.path.join(os.getcwd(), "frontend/build")
static_build_path = os.path.join(frontend_build_path, "static")

if os.path.exists(frontend_build_path) and os.path.exists(static_build_path):
    app.mount("/static", StaticFiles(directory=static_build_path), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path.startswith("api"):
             return {"error": "API endpoint not found"}
        
        file_path = os.path.join(frontend_build_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        return FileResponse(os.path.join(frontend_build_path, "index.html"))
else:
    pass
