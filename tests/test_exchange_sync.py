"""
Tests for ExchangeSyncService - Exchange synchronization functionality.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.exchange_sync import ExchangeSyncService
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    return user


@pytest.fixture
def mock_exchange_connector():
    connector = AsyncMock()
    return connector


@pytest.fixture
def mock_dca_order_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_position_group_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def sync_service(mock_session, mock_user, mock_exchange_connector, mock_dca_order_repo, mock_position_group_repo):
    return ExchangeSyncService(
        session=mock_session,
        user=mock_user,
        exchange_connector=mock_exchange_connector,
        dca_order_repository=mock_dca_order_repo,
        position_group_repository=mock_position_group_repo
    )


class TestExchangeSyncServiceInit:
    """Test ExchangeSyncService initialization."""

    @pytest.mark.asyncio
    async def test_init_with_default_repositories(self, mock_session, mock_user, mock_exchange_connector):
        """Test initialization with default repositories."""
        with patch('app.services.exchange_sync.DCAOrderRepository') as MockDCARepo, \
             patch('app.services.exchange_sync.PositionGroupRepository') as MockPGRepo:
            service = ExchangeSyncService(
                session=mock_session,
                user=mock_user,
                exchange_connector=mock_exchange_connector
            )
            assert service.session == mock_session
            assert service.user == mock_user
            assert service.exchange_connector == mock_exchange_connector
            MockDCARepo.assert_called_once_with(mock_session)
            MockPGRepo.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_init_with_custom_repositories(self, sync_service, mock_dca_order_repo, mock_position_group_repo):
        """Test initialization with custom repositories."""
        assert sync_service.dca_order_repo == mock_dca_order_repo
        assert sync_service.position_group_repo == mock_position_group_repo


class TestSyncOrdersWithExchange:
    """Test sync_orders_with_exchange method."""

    @pytest.mark.asyncio
    async def test_sync_position_group_not_found(self, sync_service, mock_position_group_repo):
        """Test sync when position group is not found."""
        mock_position_group_repo.get.return_value = None
        position_group_id = uuid.uuid4()

        result = await sync_service.sync_orders_with_exchange(position_group_id)

        assert result["synced"] == 0
        assert result["updated"] == 0
        assert result["not_found"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_sync_unauthorized_user(self, sync_service, mock_position_group_repo, mock_user):
        """Test sync when user is not authorized for position group."""
        position_group = MagicMock()
        position_group.user_id = uuid.uuid4()  # Different from mock_user.id
        mock_position_group_repo.get.return_value = position_group

        result = await sync_service.sync_orders_with_exchange(uuid.uuid4())

        assert result["synced"] == 0
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_sync_orders_success(self, sync_service, mock_position_group_repo, mock_dca_order_repo, mock_exchange_connector, mock_user):
        """Test successful order sync."""
        position_group_id = uuid.uuid4()
        position_group = MagicMock()
        position_group.user_id = mock_user.id
        mock_position_group_repo.get.return_value = position_group

        # Create mock orders
        order1 = MagicMock()
        order1.id = uuid.uuid4()
        order1.exchange_order_id = "ex123"
        order1.symbol = "BTCUSDT"
        order1.status = OrderStatus.OPEN.value

        mock_dca_order_repo.get_by_group_id.return_value = [order1]

        # Mock exchange response - order already synced (same status)
        mock_exchange_connector.get_order_status.return_value = {
            "status": "open",
            "filled": 0,
            "average": None
        }

        result = await sync_service.sync_orders_with_exchange(position_group_id)

        assert result["synced"] == 1
        assert result["updated"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_sync_orders_with_status_update(self, sync_service, mock_position_group_repo, mock_dca_order_repo, mock_exchange_connector, mock_user):
        """Test order sync with status update from OPEN to FILLED."""
        position_group_id = uuid.uuid4()
        position_group = MagicMock()
        position_group.user_id = mock_user.id
        mock_position_group_repo.get.return_value = position_group

        # Create mock order in OPEN status
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex456"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value
        order.filled_at = None

        mock_dca_order_repo.get_by_group_id.return_value = [order]

        # Mock exchange response - order is now FILLED
        mock_exchange_connector.get_order_status.return_value = {
            "status": "filled",
            "filled": 0.5,
            "average": 50000.0
        }

        result = await sync_service.sync_orders_with_exchange(position_group_id, update_local=True)

        assert result["updated"] == 1
        mock_dca_order_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_orders_skip_without_exchange_id(self, sync_service, mock_position_group_repo, mock_dca_order_repo, mock_user):
        """Test that orders without exchange_order_id are skipped."""
        position_group_id = uuid.uuid4()
        position_group = MagicMock()
        position_group.user_id = mock_user.id
        mock_position_group_repo.get.return_value = position_group

        # Create mock order without exchange_order_id
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = None
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.TRIGGER_PENDING.value

        mock_dca_order_repo.get_by_group_id.return_value = [order]

        result = await sync_service.sync_orders_with_exchange(position_group_id)

        assert result["synced"] == 0
        assert len(result["details"]) == 1
        assert result["details"][0]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_sync_orders_exception_handling(self, sync_service, mock_position_group_repo, mock_dca_order_repo, mock_exchange_connector, mock_user):
        """Test exception handling during sync."""
        position_group_id = uuid.uuid4()
        position_group = MagicMock()
        position_group.user_id = mock_user.id
        mock_position_group_repo.get.return_value = position_group

        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex789"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value

        mock_dca_order_repo.get_by_group_id.return_value = [order]
        mock_exchange_connector.get_order_status.side_effect = Exception("API error")

        result = await sync_service.sync_orders_with_exchange(position_group_id)

        assert result["errors"] == 1

    @pytest.mark.asyncio
    async def test_sync_orders_outer_exception(self, sync_service, mock_position_group_repo):
        """Test handling of outer exception."""
        mock_position_group_repo.get.side_effect = Exception("Database error")

        result = await sync_service.sync_orders_with_exchange(uuid.uuid4())

        assert result["errors"] == 1


class TestSyncSingleOrder:
    """Test _sync_single_order method."""

    @pytest.mark.asyncio
    async def test_sync_order_not_found_on_exchange(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test order not found on exchange is marked as cancelled."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_missing"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value

        mock_exchange_connector.get_order_status.side_effect = Exception("Order not found")

        result = await sync_service._sync_single_order(order, update_local=True)

        assert result["status"] == "not_found"
        mock_dca_order_repo.update.assert_called_once()
        assert order.status == OrderStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_sync_order_not_found_trigger_pending(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test trigger pending order not found on exchange is marked as cancelled."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_trigger"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.TRIGGER_PENDING.value

        mock_exchange_connector.get_order_status.side_effect = Exception("order does not exist")

        result = await sync_service._sync_single_order(order, update_local=True)

        assert result["status"] == "not_found"
        mock_dca_order_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_order_cancelled_status(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test sync with cancelled status from exchange."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_cancelled"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value

        mock_exchange_connector.get_order_status.return_value = {
            "status": "cancelled",
            "filled": 0,
            "average": None
        }

        result = await sync_service._sync_single_order(order, update_local=True)

        assert result["status"] == "updated"
        assert result["new_status"] == OrderStatus.CANCELLED.value
        mock_dca_order_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_order_expired_status(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test sync with expired status from exchange."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_expired"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value

        mock_exchange_connector.get_order_status.return_value = {
            "status": "expired",
            "filled": 0,
            "average": None
        }

        result = await sync_service._sync_single_order(order, update_local=True)

        assert result["status"] == "updated"
        assert result["new_status"] == OrderStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_sync_order_rejected_status(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test sync with rejected status from exchange."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_rejected"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value

        mock_exchange_connector.get_order_status.return_value = {
            "status": "rejected",
            "filled": 0,
            "average": None
        }

        result = await sync_service._sync_single_order(order, update_local=True)

        assert result["status"] == "updated"
        assert result["new_status"] == OrderStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_sync_order_closed_status(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test sync with closed status from exchange (Binance uses 'closed' for filled)."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_closed"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value
        order.filled_at = None

        mock_exchange_connector.get_order_status.return_value = {
            "status": "closed",
            "filled": 1.0,
            "average": 45000.0
        }

        result = await sync_service._sync_single_order(order, update_local=True)

        assert result["status"] == "updated"
        assert result["new_status"] == OrderStatus.FILLED.value

    @pytest.mark.asyncio
    async def test_sync_order_no_update_when_flag_false(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test that no DB update happens when update_local=False."""
        order = MagicMock()
        order.id = uuid.uuid4()
        order.exchange_order_id = "ex_test"
        order.symbol = "BTCUSDT"
        order.status = OrderStatus.OPEN.value

        mock_exchange_connector.get_order_status.return_value = {
            "status": "filled",
            "filled": 1.0,
            "average": 45000.0
        }

        result = await sync_service._sync_single_order(order, update_local=False)

        assert result["status"] == "updated"
        mock_dca_order_repo.update.assert_not_called()


class TestDetectOrphanedExchangeOrders:
    """Test detect_orphaned_exchange_orders method."""

    @pytest.mark.asyncio
    async def test_detect_orphaned_orders_found(self, sync_service, mock_exchange_connector, mock_dca_order_repo, mock_user):
        """Test detection of orphaned orders on exchange."""
        symbol = "BTCUSDT"

        # Mock exchange returns 2 orders
        mock_exchange_connector.fetch_open_orders.return_value = [
            {"id": "ex1", "symbol": symbol, "side": "buy", "type": "limit", "price": 50000, "amount": 0.1, "status": "open", "datetime": "2025-01-01T00:00:00"},
            {"id": "ex2", "symbol": symbol, "side": "sell", "type": "limit", "price": 55000, "amount": 0.1, "status": "open", "datetime": "2025-01-01T00:00:00"}
        ]

        # Mock local orders only has ex1
        local_order = MagicMock()
        local_order.exchange_order_id = "ex1"
        mock_dca_order_repo.get_by_symbol_and_user.return_value = [local_order]

        orphaned = await sync_service.detect_orphaned_exchange_orders(symbol)

        assert len(orphaned) == 1
        assert orphaned[0]["exchange_order_id"] == "ex2"

    @pytest.mark.asyncio
    async def test_detect_orphaned_orders_none_found(self, sync_service, mock_exchange_connector, mock_dca_order_repo, mock_user):
        """Test when no orphaned orders exist."""
        symbol = "BTCUSDT"

        mock_exchange_connector.fetch_open_orders.return_value = [
            {"id": "ex1", "symbol": symbol, "side": "buy", "type": "limit", "price": 50000, "amount": 0.1, "status": "open", "datetime": "2025-01-01T00:00:00"}
        ]

        local_order = MagicMock()
        local_order.exchange_order_id = "ex1"
        mock_dca_order_repo.get_by_symbol_and_user.return_value = [local_order]

        orphaned = await sync_service.detect_orphaned_exchange_orders(symbol)

        assert len(orphaned) == 0

    @pytest.mark.asyncio
    async def test_detect_orphaned_orders_exception(self, sync_service, mock_exchange_connector):
        """Test handling of exception during orphan detection."""
        mock_exchange_connector.fetch_open_orders.side_effect = Exception("Exchange error")

        orphaned = await sync_service.detect_orphaned_exchange_orders("BTCUSDT")

        assert orphaned == []

    @pytest.mark.asyncio
    async def test_detect_orphaned_orders_empty_id(self, sync_service, mock_exchange_connector, mock_dca_order_repo):
        """Test handling of exchange orders with empty ID."""
        symbol = "BTCUSDT"

        mock_exchange_connector.fetch_open_orders.return_value = [
            {"id": "", "symbol": symbol, "side": "buy", "type": "limit"},
            {"id": "ex1", "symbol": symbol, "side": "buy", "type": "limit"}
        ]

        mock_dca_order_repo.get_by_symbol_and_user.return_value = []

        orphaned = await sync_service.detect_orphaned_exchange_orders(symbol)

        # Only ex1 should be in orphaned (empty ID is skipped)
        assert len(orphaned) == 1
        assert orphaned[0]["exchange_order_id"] == "ex1"


class TestCleanupStaleLocalOrders:
    """Test cleanup_stale_local_orders method."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_orders_success(self, sync_service, mock_dca_order_repo, mock_exchange_connector):
        """Test successful cleanup of stale orders."""
        position_group_id = uuid.uuid4()

        # Create a stale open order (older than 48 hours)
        stale_order = MagicMock()
        stale_order.id = uuid.uuid4()
        stale_order.exchange_order_id = "ex_stale"
        stale_order.symbol = "BTCUSDT"
        stale_order.status = OrderStatus.OPEN.value
        stale_order.submitted_at = datetime.utcnow() - timedelta(hours=72)

        mock_dca_order_repo.get_by_group_id.return_value = [stale_order]

        # Mock exchange response - order filled
        mock_exchange_connector.get_order_status.return_value = {
            "status": "filled",
            "filled": 1.0,
            "average": 50000.0
        }

        result = await sync_service.cleanup_stale_local_orders(position_group_id)

        assert result["checked"] == 1
        assert result["cleaned"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_skips_non_open_orders(self, sync_service, mock_dca_order_repo):
        """Test that non-OPEN orders are skipped during cleanup."""
        position_group_id = uuid.uuid4()

        filled_order = MagicMock()
        filled_order.status = OrderStatus.FILLED.value
        filled_order.submitted_at = datetime.utcnow() - timedelta(hours=72)

        mock_dca_order_repo.get_by_group_id.return_value = [filled_order]

        result = await sync_service.cleanup_stale_local_orders(position_group_id)

        assert result["checked"] == 0
        assert result["cleaned"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_skips_recent_orders(self, sync_service, mock_dca_order_repo):
        """Test that recent orders are skipped during cleanup."""
        position_group_id = uuid.uuid4()

        recent_order = MagicMock()
        recent_order.status = OrderStatus.OPEN.value
        recent_order.submitted_at = datetime.utcnow() - timedelta(hours=1)  # Only 1 hour old

        mock_dca_order_repo.get_by_group_id.return_value = [recent_order]

        result = await sync_service.cleanup_stale_local_orders(position_group_id)

        assert result["checked"] == 0
        assert result["cleaned"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_handles_exception(self, sync_service, mock_dca_order_repo, mock_exchange_connector):
        """Test cleanup handles exception for individual orders."""
        position_group_id = uuid.uuid4()

        stale_order = MagicMock()
        stale_order.id = uuid.uuid4()
        stale_order.exchange_order_id = "ex_error"
        stale_order.symbol = "BTCUSDT"
        stale_order.status = OrderStatus.OPEN.value
        stale_order.submitted_at = datetime.utcnow() - timedelta(hours=72)

        mock_dca_order_repo.get_by_group_id.return_value = [stale_order]
        mock_exchange_connector.get_order_status.side_effect = Exception("API error")

        result = await sync_service.cleanup_stale_local_orders(position_group_id)

        assert result["checked"] == 1
        assert result["errors"] == 1

    @pytest.mark.asyncio
    async def test_cleanup_handles_outer_exception(self, sync_service, mock_dca_order_repo):
        """Test cleanup handles outer exception."""
        mock_dca_order_repo.get_by_group_id.side_effect = Exception("DB error")

        result = await sync_service.cleanup_stale_local_orders(uuid.uuid4())

        assert result["checked"] == 0
        assert result["cleaned"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_not_found_status(self, sync_service, mock_dca_order_repo, mock_exchange_connector):
        """Test cleanup with not_found status from sync."""
        position_group_id = uuid.uuid4()

        stale_order = MagicMock()
        stale_order.id = uuid.uuid4()
        stale_order.exchange_order_id = "ex_missing"
        stale_order.symbol = "BTCUSDT"
        stale_order.status = OrderStatus.OPEN.value
        stale_order.submitted_at = datetime.utcnow() - timedelta(hours=72)

        mock_dca_order_repo.get_by_group_id.return_value = [stale_order]
        mock_exchange_connector.get_order_status.side_effect = Exception("Order not found")

        result = await sync_service.cleanup_stale_local_orders(position_group_id)

        assert result["checked"] == 1
        assert result["cleaned"] == 1
