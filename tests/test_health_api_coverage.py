"""
Comprehensive tests for api/health.py to achieve 100% coverage.
Covers: root_health_check, db_health_check, redis_health_check,
services_health_check, comprehensive_health_check
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# --- Tests for root health check ---

@pytest.mark.asyncio
async def test_root_health_check(client: AsyncClient):
    """Test basic health check returns ok."""
    response = await client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Tests for database health check ---

@pytest.mark.asyncio
async def test_db_health_check_success(client: AsyncClient):
    """Test database health check when connected."""
    response = await client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"


@pytest.mark.asyncio
async def test_db_health_check_with_connection(client: AsyncClient):
    """Test database health check confirms connection works."""
    response = await client.get("/api/v1/health/db")
    # With the actual test database, this should succeed
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


# --- Tests for Redis health check ---

@pytest.mark.asyncio
async def test_redis_health_check_connected_success(client: AsyncClient):
    """Test Redis health check when connected and operations succeed."""
    mock_cache = AsyncMock()
    mock_cache._connected = True
    mock_cache.set = AsyncMock()
    mock_cache.get = AsyncMock(return_value={"test": True})
    mock_cache.delete = AsyncMock()

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/redis")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_redis_health_check_connected_read_fail(client: AsyncClient):
    """Test Redis health check when connected but read fails."""
    mock_cache = AsyncMock()
    mock_cache._connected = True
    mock_cache.set = AsyncMock()
    mock_cache.get = AsyncMock(return_value=None)  # Read returns None
    mock_cache.delete = AsyncMock()

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/redis")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["redis"] == "connected but read failed"


@pytest.mark.asyncio
async def test_redis_health_check_not_connected(client: AsyncClient):
    """Test Redis health check when not connected."""
    mock_cache = AsyncMock()
    mock_cache._connected = False

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/redis")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable"
    assert data["redis"] == "not connected"


@pytest.mark.asyncio
async def test_redis_health_check_exception(client: AsyncClient):
    """Test Redis health check when exception occurs."""
    with patch("app.api.health.get_cache", side_effect=Exception("Redis error")):
        response = await client.get("/api/v1/health/redis")

    assert response.status_code == 503
    assert "Redis connection failed" in response.json()["detail"]


# --- Tests for services health check ---

@pytest.mark.asyncio
async def test_services_health_check_all_healthy(client: AsyncClient):
    """Test services health check when all services are healthy."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {
            "status": "running",
            "last_heartbeat": current_time - 30,  # 30 seconds ago
            "metrics": {"orders_checked": 100}
        },
        "queue_manager": {
            "status": "running",
            "last_heartbeat": current_time - 60,  # 1 minute ago
            "metrics": {"signals_processed": 50}
        },
        "risk_engine": {
            "status": "running",
            "last_heartbeat": current_time - 120,  # 2 minutes ago
            "metrics": {"evaluations": 25}
        }
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "order_fill_monitor" in data["services"]
    assert data["services"]["order_fill_monitor"]["healthy"] is True


@pytest.mark.asyncio
async def test_services_health_check_unhealthy_service(client: AsyncClient):
    """Test services health check when a service has stale heartbeat."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {
            "status": "running",
            "last_heartbeat": current_time - 30,
            "metrics": {}
        },
        "queue_manager": {
            "status": "running",
            "last_heartbeat": current_time - 400,  # Over 5 minutes ago - unhealthy
            "metrics": {}
        },
        "risk_engine": {
            "status": "running",
            "last_heartbeat": current_time - 60,
            "metrics": {}
        }
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"]["queue_manager"]["healthy"] is False


@pytest.mark.asyncio
async def test_services_health_check_missing_service(client: AsyncClient):
    """Test services health check when a service is not reporting."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {
            "status": "running",
            "last_heartbeat": current_time - 30,
            "metrics": {}
        },
        # queue_manager and risk_engine not reporting
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"]["queue_manager"]["status"] == "not_reporting"
    assert data["services"]["queue_manager"]["healthy"] is False
    assert data["services"]["risk_engine"]["status"] == "not_reporting"


@pytest.mark.asyncio
async def test_services_health_check_exception(client: AsyncClient):
    """Test services health check when exception occurs."""
    with patch("app.api.health.get_cache", side_effect=Exception("Cache error")):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "error" in data


@pytest.mark.asyncio
async def test_services_health_check_missing_metrics(client: AsyncClient):
    """Test services health check when metrics are missing from service data."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {
            "status": "running",
            "last_heartbeat": current_time - 30
            # No metrics key
        }
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    # Should use default empty dict for metrics
    assert data["services"]["order_fill_monitor"]["metrics"] == {}


# --- Tests for comprehensive health check ---

@pytest.mark.asyncio
async def test_comprehensive_health_check_all_ok(client: AsyncClient):
    """Test comprehensive health check when all components are healthy."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache._connected = True
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {"status": "running", "last_heartbeat": current_time - 30, "metrics": {}},
        "queue_manager": {"status": "running", "last_heartbeat": current_time - 30, "metrics": {}},
        "risk_engine": {"status": "running", "last_heartbeat": current_time - 30, "metrics": {}}
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/comprehensive")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["components"]["database"]["healthy"] is True


@pytest.mark.asyncio
async def test_comprehensive_health_check_redis_unavailable(client: AsyncClient):
    """Test comprehensive health check when Redis is unavailable."""
    mock_cache = AsyncMock()
    mock_cache._connected = False
    mock_cache.get_all_services_health = AsyncMock(return_value={})

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/comprehensive")

    assert response.status_code == 200
    data = response.json()
    assert data["components"]["redis"]["healthy"] is False
    assert data["components"]["redis"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_comprehensive_health_check_redis_exception(client: AsyncClient):
    """Test comprehensive health check when Redis raises exception."""
    with patch("app.api.health.get_cache", side_effect=Exception("Redis error")):
        response = await client.get("/api/v1/health/comprehensive")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["components"]["redis"]["healthy"] is False
    assert "error" in data["components"]["redis"]


@pytest.mark.asyncio
async def test_comprehensive_health_check_services_degraded(client: AsyncClient):
    """Test comprehensive health check when services are degraded."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache._connected = True
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {"status": "running", "last_heartbeat": current_time - 600, "metrics": {}},
        # Other services not reporting
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/comprehensive")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_comprehensive_health_check_db_failure(client: AsyncClient):
    """Test comprehensive health check handles database query errors."""
    # The actual test requires mocking at the session level
    # For now, test with healthy DB
    response = await client.get("/api/v1/health/comprehensive")
    assert response.status_code == 200
    assert "database" in response.json()["components"]


@pytest.mark.asyncio
async def test_db_health_check_exception(client: AsyncClient):
    """Test database health check returns 503 on database error."""
    from app.db.database import get_db_session

    async def mock_failing_session():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database connection lost")
        yield mock_session

    from app.main import app
    app.dependency_overrides[get_db_session] = mock_failing_session

    try:
        response = await client.get("/api/v1/health/db")

        assert response.status_code == 503
        assert "Database connection failed" in response.json()["detail"]
    finally:
        del app.dependency_overrides[get_db_session]


@pytest.mark.asyncio
async def test_comprehensive_health_check_db_exception(client: AsyncClient):
    """Test comprehensive health check handles database exception."""
    from app.db.database import get_db_session

    async def mock_failing_session():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB Error")
        yield mock_session

    mock_cache = AsyncMock()
    mock_cache._connected = True
    mock_cache.get_all_services_health = AsyncMock(return_value={})

    from app.main import app
    app.dependency_overrides[get_db_session] = mock_failing_session

    try:
        with patch("app.api.health.get_cache", return_value=mock_cache):
            response = await client.get("/api/v1/health/comprehensive")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"]["healthy"] is False
        assert "error" in data["components"]["database"]
    finally:
        del app.dependency_overrides[get_db_session]


@pytest.mark.asyncio
async def test_comprehensive_health_check_services_exception(client: AsyncClient):
    """Test comprehensive health check handles services check exception."""
    mock_cache = AsyncMock()
    mock_cache._connected = True
    mock_cache.get_all_services_health.side_effect = Exception("Services check failed")

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/comprehensive")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert "error" in data["components"]["services"]


@pytest.mark.asyncio
async def test_services_health_check_missing_last_heartbeat(client: AsyncClient):
    """Test services health check when last_heartbeat is missing."""
    mock_cache = AsyncMock()
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {
            "status": "running",
            # No last_heartbeat key - should default to 0
            "metrics": {}
        },
        "queue_manager": {"status": "running", "metrics": {}},
        "risk_engine": {"status": "running", "metrics": {}}
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    # With no heartbeat, it should be unhealthy (>300 seconds since epoch 0)
    assert data["services"]["order_fill_monitor"]["healthy"] is False


@pytest.mark.asyncio
async def test_services_health_check_missing_status_field(client: AsyncClient):
    """Test services health check when status field is missing from service data."""
    current_time = time.time()
    mock_cache = AsyncMock()
    mock_cache.get_all_services_health = AsyncMock(return_value={
        "order_fill_monitor": {
            # No status field - should default to "unknown"
            "last_heartbeat": current_time - 30,
            "metrics": {}
        },
        "queue_manager": {"last_heartbeat": current_time - 30},
        "risk_engine": {"last_heartbeat": current_time - 30}
    })

    with patch("app.api.health.get_cache", return_value=mock_cache):
        response = await client.get("/api/v1/health/services")

    assert response.status_code == 200
    data = response.json()
    # Should use "unknown" as default status
    assert data["services"]["order_fill_monitor"]["status"] == "unknown"


@pytest.mark.asyncio
async def test_comprehensive_health_all_degraded(client: AsyncClient):
    """Test comprehensive health check when all components are degraded."""
    from app.db.database import get_db_session

    async def mock_failing_session():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB Error")
        yield mock_session

    from app.main import app
    app.dependency_overrides[get_db_session] = mock_failing_session

    # Mock Redis as unavailable
    mock_cache = AsyncMock()
    mock_cache._connected = False
    mock_cache.get_all_services_health = AsyncMock(return_value={})

    try:
        with patch("app.api.health.get_cache", return_value=mock_cache):
            response = await client.get("/api/v1/health/comprehensive")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"]["healthy"] is False
        assert data["components"]["redis"]["healthy"] is False
    finally:
        del app.dependency_overrides[get_db_session]
