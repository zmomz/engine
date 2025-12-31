"""
Tests for queue API endpoints.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal
import uuid

from app.main import app
from app.api.queue import get_queue_manager_service
from app.api.dependencies.users import get_current_active_user


@pytest.fixture
def sample_queued_signal():
    """Create a sample queued signal."""
    signal = MagicMock()
    signal.id = uuid.uuid4()
    signal.user_id = uuid.uuid4()
    signal.symbol = "BTCUSDT"
    signal.exchange = "binance"
    signal.side = "buy"
    signal.timeframe = 60
    signal.status = "queued"
    signal.priority = 50
    signal.position_size_usd = Decimal("100")
    signal.entry_price = Decimal("50000")
    signal.created_at = datetime.utcnow()
    signal.updated_at = datetime.utcnow()
    signal.signal_data = {}
    signal.raw_payload = {}
    signal.queue_position = 1
    signal.max_pyramids = 2
    signal.replacement_count = 0
    signal.config_snapshot = None
    return signal


@pytest.mark.asyncio
async def test_get_all_queued_signals(authorized_client):
    """Test GET /queue/ endpoint."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    mock_service = AsyncMock()
    mock_service.get_all_queued_signals = AsyncMock(return_value=[])

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user
    app.dependency_overrides[get_queue_manager_service] = lambda: mock_service

    try:
        response = await authorized_client.get("/api/v1/queue/")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        del app.dependency_overrides[get_current_active_user]
        del app.dependency_overrides[get_queue_manager_service]


@pytest.mark.asyncio
async def test_get_queue_history(authorized_client):
    """Test GET /queue/history endpoint."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    mock_service = AsyncMock()
    mock_service.get_queue_history = AsyncMock(return_value=[])

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user
    app.dependency_overrides[get_queue_manager_service] = lambda: mock_service

    try:
        response = await authorized_client.get("/api/v1/queue/history?limit=50")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        del app.dependency_overrides[get_current_active_user]
        del app.dependency_overrides[get_queue_manager_service]


@pytest.mark.asyncio
async def test_promote_queued_signal_not_found(authorized_client):
    """Test POST /queue/{signal_id}/promote endpoint - not found."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    signal_id = str(uuid.uuid4())

    mock_service = AsyncMock()
    mock_service.promote_specific_signal = AsyncMock(return_value=None)

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user
    app.dependency_overrides[get_queue_manager_service] = lambda: mock_service

    try:
        response = await authorized_client.post(f"/api/v1/queue/{signal_id}/promote")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        del app.dependency_overrides[get_current_active_user]
        del app.dependency_overrides[get_queue_manager_service]


@pytest.mark.asyncio
async def test_remove_queued_signal_success(authorized_client):
    """Test DELETE /queue/{signal_id} endpoint - success."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    signal_id = str(uuid.uuid4())

    mock_service = AsyncMock()
    mock_service.remove_from_queue = AsyncMock(return_value=True)

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user
    app.dependency_overrides[get_queue_manager_service] = lambda: mock_service

    try:
        response = await authorized_client.delete(f"/api/v1/queue/{signal_id}")
        assert response.status_code == 200
        assert "removed successfully" in response.json()["message"]
    finally:
        del app.dependency_overrides[get_current_active_user]
        del app.dependency_overrides[get_queue_manager_service]


@pytest.mark.asyncio
async def test_remove_queued_signal_not_found(authorized_client):
    """Test DELETE /queue/{signal_id} endpoint - not found."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    signal_id = str(uuid.uuid4())

    mock_service = AsyncMock()
    mock_service.remove_from_queue = AsyncMock(return_value=False)

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user
    app.dependency_overrides[get_queue_manager_service] = lambda: mock_service

    try:
        response = await authorized_client.delete(f"/api/v1/queue/{signal_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        del app.dependency_overrides[get_current_active_user]
        del app.dependency_overrides[get_queue_manager_service]


@pytest.mark.asyncio
async def test_force_add_to_pool_not_found(authorized_client):
    """Test POST /queue/{signal_id}/force-add endpoint - not found."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    signal_id = str(uuid.uuid4())

    mock_service = AsyncMock()
    mock_service.force_add_specific_signal_to_pool = AsyncMock(return_value=None)

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user
    app.dependency_overrides[get_queue_manager_service] = lambda: mock_service

    try:
        response = await authorized_client.post(f"/api/v1/queue/{signal_id}/force-add")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        del app.dependency_overrides[get_current_active_user]
        del app.dependency_overrides[get_queue_manager_service]


class TestGetQueueManagerService:
    """Tests for get_queue_manager_service dependency."""

    def test_get_queue_manager_service(self):
        """Test the dependency function."""
        mock_request = MagicMock()
        mock_service = MagicMock()
        mock_request.app.state.queue_manager_service = mock_service

        result = get_queue_manager_service(mock_request)

        assert result == mock_service
