import time
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db_session
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter()


async def _measure_query_latency(session: AsyncSession) -> float:
    """Measure database query latency in milliseconds."""
    start = time.perf_counter()
    await session.execute(text("SELECT 1"))
    end = time.perf_counter()
    return (end - start) * 1000  # Convert to milliseconds


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


@router.get("/db/detailed")
async def db_detailed_health_check(session: AsyncSession = Depends(get_db_session)):
    """
    Comprehensive database health check with detailed metrics.

    Returns:
        - Connection status
        - Query latency (ms)
        - Pool statistics
        - Table row counts for key tables
    """
    result = {
        "status": "ok",
        "healthy": True,
        "timestamp": time.time(),
        "connection": {"status": "connected"},
        "latency": {},
        "pool": {},
        "tables": {}
    }

    try:
        # Measure query latency (multiple samples for accuracy)
        latencies = []
        for _ in range(3):
            latency = await _measure_query_latency(session)
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        result["latency"] = {
            "avg_ms": round(avg_latency, 2),
            "min_ms": round(min(latencies), 2),
            "max_ms": round(max(latencies), 2),
            "samples": len(latencies)
        }

        # Latency thresholds
        if avg_latency > 100:
            result["status"] = "degraded"
            result["latency"]["warning"] = "High latency detected"
        elif avg_latency > 500:
            result["healthy"] = False
            result["latency"]["warning"] = "Critical latency"

    except Exception as e:
        result["status"] = "error"
        result["healthy"] = False
        result["connection"] = {"status": "error", "error": str(e)}
        return result

    try:
        # Get connection pool statistics from the engine
        bind = session.get_bind()
        if hasattr(bind, 'pool'):
            pool = bind.pool
            result["pool"] = {
                "size": getattr(pool, 'size', None),
                "checked_in": getattr(pool, 'checkedin', lambda: None)() if hasattr(pool, 'checkedin') else None,
                "checked_out": getattr(pool, 'checkedout', lambda: None)() if hasattr(pool, 'checkedout') else None,
                "overflow": getattr(pool, 'overflow', lambda: None)() if hasattr(pool, 'overflow') else None,
            }
    except Exception as e:
        result["pool"] = {"error": str(e)}

    try:
        # Get row counts for key tables (lightweight check)
        tables_to_check = [
            "users",
            "position_groups",
            "dca_orders"
        ]

        for table in tables_to_check:
            try:
                count_result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                count = count_result.scalar()
                result["tables"][table] = {"row_count": count}
            except Exception:
                # Table might not exist or other issue - skip
                pass

    except Exception as e:
        result["tables"]["error"] = str(e)

    return result


@router.get("/watchdog")
async def watchdog_health_check(request: Request):
    """
    Get the status of the task watchdog and all monitored tasks.

    Returns health status for:
    - OrderFillMonitor
    - QueueManager
    - RiskEngine
    """
    try:
        # Check if watchdog exists on app state
        if not hasattr(request.app.state, "watchdog"):
            return {
                "status": "not_running",
                "message": "Watchdog not started (this worker may not be the leader)"
            }

        watchdog = request.app.state.watchdog
        summary = watchdog.get_summary()

        # Determine overall status
        if summary["unhealthy"] > 0:
            overall_status = "unhealthy"
        elif summary["degraded"] > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "summary": {
                "healthy_tasks": summary["healthy"],
                "degraded_tasks": summary["degraded"],
                "unhealthy_tasks": summary["unhealthy"],
                "total_tasks": summary["total"]
            },
            "tasks": summary["tasks"]
        }
    except Exception as e:
        logger.error(f"Watchdog health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/circuit-breakers")
async def circuit_breakers_health_check():
    """
    Get the status of all exchange circuit breakers.

    Returns the state (closed, open, half_open) for each exchange.
    """
    try:
        from app.core.circuit_breaker import get_circuit_registry

        registry = get_circuit_registry()
        metrics = registry.get_all_metrics()

        # Determine overall status
        has_open = any(m.get("state") == "open" for m in metrics.values())
        has_half_open = any(m.get("state") == "half_open" for m in metrics.values())

        if has_open:
            overall_status = "degraded"
        elif has_half_open:
            overall_status = "recovering"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "circuits": metrics
        }
    except Exception as e:
        logger.error(f"Circuit breaker health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


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
async def comprehensive_health_check(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Comprehensive health check including database, Redis, services, watchdog, and circuit breakers.
    """
    result = {
        "status": "ok",
        "timestamp": time.time(),
        "components": {}
    }

    overall_healthy = True

    # Check database with latency
    try:
        latency = await _measure_query_latency(session)
        db_healthy = latency < 500  # 500ms threshold
        result["components"]["database"] = {
            "status": "ok" if db_healthy else "degraded",
            "healthy": db_healthy,
            "latency_ms": round(latency, 2)
        }
        if not db_healthy:
            overall_healthy = False
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

    # Check circuit breakers
    try:
        circuits_result = await circuit_breakers_health_check()
        result["components"]["circuit_breakers"] = circuits_result
        if circuits_result.get("status") == "degraded":
            overall_healthy = False
    except Exception as e:
        result["components"]["circuit_breakers"] = {"status": "error", "error": str(e)}

    # Check watchdog (if available)
    try:
        watchdog_result = await watchdog_health_check(request)
        if watchdog_result.get("status") != "not_running":
            result["components"]["watchdog"] = watchdog_result
            if watchdog_result.get("status") not in ["healthy", "not_running"]:
                overall_healthy = False
    except Exception as e:
        result["components"]["watchdog"] = {"status": "error", "error": str(e)}

    result["status"] = "ok" if overall_healthy else "degraded"

    return result
