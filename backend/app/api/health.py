import time
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db_session
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def root_health_check():
    return {"status": "ok"}


@router.get("/db")
async def db_health_check(session: AsyncSession = Depends(get_db_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {e}",
        )


@router.get("/redis")
async def redis_health_check():
    """Check Redis connection status."""
    try:
        cache = await get_cache()
        if cache._connected:
            # Test with a simple operation
            test_key = "health_check_test"
            await cache.set(test_key, {"test": True}, ttl=10)
            result = await cache.get(test_key)
            await cache.delete(test_key)

            if result:
                return {"status": "ok", "redis": "connected"}
            else:
                return {"status": "degraded", "redis": "connected but read failed"}
        else:
            return {"status": "unavailable", "redis": "not connected"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis connection failed: {e}",
        )


@router.get("/services")
async def services_health_check():
    """
    Get health status of all background services.

    Returns status, last heartbeat, and metrics for:
    - OrderFillMonitorService
    - QueueManagerService
    - RiskEngineService
    """
    try:
        cache = await get_cache()
        services_health = await cache.get_all_services_health()

        current_time = time.time()
        result = {
            "status": "ok",
            "services": {}
        }

        # Expected services
        expected_services = ["order_fill_monitor", "queue_manager", "risk_engine"]

        overall_healthy = True

        for service_name in expected_services:
            if service_name in services_health:
                service_data = services_health[service_name]
                last_heartbeat = service_data.get("last_heartbeat", 0)
                seconds_since_heartbeat = current_time - last_heartbeat

                # Consider unhealthy if no heartbeat in 5 minutes
                is_healthy = seconds_since_heartbeat < 300
                if not is_healthy:
                    overall_healthy = False

                result["services"][service_name] = {
                    "status": service_data.get("status", "unknown"),
                    "healthy": is_healthy,
                    "last_heartbeat_seconds_ago": round(seconds_since_heartbeat, 1),
                    "metrics": service_data.get("metrics", {})
                }
            else:
                # Service not reporting - could be not started or unhealthy
                overall_healthy = False
                result["services"][service_name] = {
                    "status": "not_reporting",
                    "healthy": False,
                    "last_heartbeat_seconds_ago": None,
                    "metrics": {}
                }

        result["status"] = "ok" if overall_healthy else "degraded"

        return result

    except Exception as e:
        logger.error(f"Services health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "services": {}
        }


@router.get("/comprehensive")
async def comprehensive_health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Comprehensive health check including database, Redis, and all services.
    """
    result = {
        "status": "ok",
        "timestamp": time.time(),
        "components": {}
    }

    overall_healthy = True

    # Check database
    try:
        await session.execute(text("SELECT 1"))
        result["components"]["database"] = {"status": "ok", "healthy": True}
    except Exception as e:
        overall_healthy = False
        result["components"]["database"] = {"status": "error", "healthy": False, "error": str(e)}

    # Check Redis
    try:
        cache = await get_cache()
        if cache._connected:
            result["components"]["redis"] = {"status": "ok", "healthy": True}
        else:
            # Redis being unavailable is degraded, not failed
            result["components"]["redis"] = {"status": "unavailable", "healthy": False}
    except Exception as e:
        result["components"]["redis"] = {"status": "error", "healthy": False, "error": str(e)}

    # Check services
    try:
        services_result = await services_health_check()
        result["components"]["services"] = services_result
        if services_result.get("status") != "ok":
            overall_healthy = False
    except Exception as e:
        overall_healthy = False
        result["components"]["services"] = {"status": "error", "error": str(e)}

    result["status"] = "ok" if overall_healthy else "degraded"

    return result
