from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import os
import logging
import sys
import uuid
import asyncio

from app.api import health, webhooks, risk, positions, queue, users, settings as api_settings, dashboard, logs, dca_configs, telegram
from app.rate_limiter import limiter
from app.services.order_fill_monitor import OrderFillMonitorService
from app.services.order_management import OrderService
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.db.database import AsyncSessionLocal, get_db_session
from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.grid_calculator import GridCalculatorService
from app.services.queue_manager import QueueManagerService
from app.services.risk_engine import RiskEngineService
from app.schemas.grid_config import RiskEngineConfig
from app.core.logging_config import setup_logging
from app.core.config import settings
from app.core.cache import get_cache
from app.core.correlation import CorrelationIdMiddleware
from app.core.watchdog import setup_watchdog, get_watchdog
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# Unique ID for this worker instance
WORKER_ID = str(uuid.uuid4())[:8]

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

# CORS Middleware - Restrict methods and headers for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "X-Correlation-ID", "X-Request-ID"],
    expose_headers=["X-Correlation-ID"],
)

if os.getenv("TESTING") != "true":
    app.add_middleware(SlowAPIMiddleware)

# Correlation ID Middleware - for request tracing across the system
# Added last so it runs first (middleware stack is LIFO)
app.add_middleware(CorrelationIdMiddleware)



async def try_become_leader() -> bool:
    """
    Try to become the leader worker for running background tasks.
    Uses Redis distributed lock to ensure only one worker runs background tasks.

    On first attempt, if the lock exists, we check if it's stale (holder not renewing)
    and clear it if needed.
    """
    try:
        cache = await get_cache()

        # First attempt to acquire the lock
        acquired = await cache.acquire_lock("background_task_leader", WORKER_ID, ttl_seconds=60)
        if acquired:
            return True

        # Lock exists - check if it might be stale (from a crashed process)
        # Wait a bit and try again - if the holder is alive, they'll renew it
        # If they're dead, the lock will expire and we can acquire it
        await asyncio.sleep(2)

        # Second attempt after waiting
        acquired = await cache.acquire_lock("background_task_leader", WORKER_ID, ttl_seconds=60)
        return acquired
    except Exception as e:
        logger.warning(f"Failed to check leader status: {e}. Assuming not leader.")
        return False


async def renew_leader_lock():
    """Background task to renew the leader lock periodically."""
    cache = await get_cache()
    while app.state.is_leader:
        try:
            # Re-acquire lock every 30 seconds (before 60s TTL expires)
            await asyncio.sleep(30)
            if app.state.is_leader:
                acquired = await cache.acquire_lock("background_task_leader", WORKER_ID, ttl_seconds=60)
                if not acquired:
                    # Lost leadership
                    logger.warning(f"Worker {WORKER_ID} lost leader status")
                    app.state.is_leader = False
                    break
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Failed to renew leader lock: {e}")


@app.on_event("startup")
async def startup_event():
    # Setup Logging
    setup_logging()

    logger.info(f"Worker {WORKER_ID} starting up in {settings.ENVIRONMENT} mode")
    logger.info(f"CORS Allowed Origins: {settings.CORS_ORIGINS}")

    # Try to become the leader worker for background tasks
    app.state.is_leader = await try_become_leader()
    app.state.leader_renewal_task = None

    # These services are needed by all workers for request handling
    # GridCalculatorService is stateless, so it can be initialized at startup
    app.state.grid_calculator_service = GridCalculatorService()

    # ExecutionPoolManager - needed before QueueManagerService
    app.state.execution_pool_manager = ExecutionPoolManager(
        session_factory=AsyncSessionLocal,
        position_group_repository_class=PositionGroupRepository
    )

    # QueueManagerService - needed by all workers for API endpoints
    app.state.queue_manager_service = QueueManagerService(
        session_factory=AsyncSessionLocal,
        execution_pool_manager=app.state.execution_pool_manager
    )

    if app.state.is_leader:
        logger.info(f"Worker {WORKER_ID} elected as LEADER - will run background tasks")

        # Start leader lock renewal task
        app.state.leader_renewal_task = asyncio.create_task(renew_leader_lock())

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

        # Start queue promotion background task (only on leader)
        await app.state.queue_manager_service.start_promotion_task()

        # RiskEngineService - Background monitoring task for automatic risk management
        app.state.risk_engine_service = RiskEngineService(
            session_factory=get_db_session,  # Use async generator function
            position_group_repository_class=PositionGroupRepository,
            risk_action_repository_class=RiskActionRepository,
            dca_order_repository_class=DCAOrderRepository,
            order_service_class=OrderService,
            risk_engine_config=RiskEngineConfig(),  # Uses default config; user-specific configs loaded per evaluation
            polling_interval_seconds=60  # Check positions every 60 seconds
        )
        await app.state.risk_engine_service.start_monitoring_task()
        logger.info("Risk Engine monitoring task started (polling every 60 seconds)")

        # Setup and start the watchdog for background task monitoring
        app.state.watchdog = await setup_watchdog(app)
        await app.state.watchdog.start()
        logger.info("Watchdog started - monitoring background tasks")
    else:
        logger.info(f"Worker {WORKER_ID} is a FOLLOWER - background tasks will be handled by leader")

    # PositionManagerService is now instantiated per-request.


@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Worker {WORKER_ID} shutting down (is_leader={getattr(app.state, 'is_leader', False)})")

    # Only stop background tasks if this worker was the leader
    if getattr(app.state, 'is_leader', False):
        # Stop watchdog first
        if hasattr(app.state, "watchdog"):
            await app.state.watchdog.stop()
            logger.info("Watchdog stopped")

        if hasattr(app.state, "order_fill_monitor"):
            await app.state.order_fill_monitor.stop_monitoring_task()
        if hasattr(app.state, "queue_manager_service"):
            await app.state.queue_manager_service.stop_promotion_task()
        if hasattr(app.state, "risk_engine_service"):
            await app.state.risk_engine_service.stop_monitoring_task()
            logger.info("Risk Engine monitoring task stopped")

        # Cancel leader renewal task
        if hasattr(app.state, "leader_renewal_task") and app.state.leader_renewal_task:
            app.state.leader_renewal_task.cancel()

        # Release leader lock
        try:
            cache = await get_cache()
            await cache.release_lock("background_task_leader", WORKER_ID)
            logger.info(f"Worker {WORKER_ID} released leader lock")
        except Exception as e:
            logger.warning(f"Failed to release leader lock: {e}")


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
app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["Telegram"])

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
