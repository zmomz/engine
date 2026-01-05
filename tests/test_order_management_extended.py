"""
Extended tests for order_management.py to improve coverage.
Covers lines: 80-90 (precision cache invalidation), 120-130 (cancel_order exception handling),
191-193 (tick_size fetch errors in place_tp_order), 262-264, 288-290, 392-396 (reconcile errors), etc.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import ccxt

from app.services.order_management import OrderService
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.exceptions import APIError, ExchangeConnectionError


@pytest.fixture
def mock_session():
    """Create mock session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Create mock user."""
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def mock_exchange_connector():
    """Create mock exchange connector."""
    return AsyncMock()


@pytest.fixture
def order_service(mock_session, mock_user, mock_exchange_connector):
    """Create OrderService with mocked dependencies."""
    service = OrderService(
        session=mock_session,
        user=mock_user,
        exchange_connector=mock_exchange_connector
    )
    service.dca_order_repository = AsyncMock()
    service.position_group_repository = AsyncMock()
    return service


class TestSubmitOrderPrecisionErrors:
    """Tests for precision-related error handling in submit_order."""

    @pytest.mark.asyncio
    async def test_submit_order_precision_error_invalidates_cache(self, order_service, mock_exchange_connector):
        """Test that precision-related APIError invalidates cache."""
        dca_order = MagicMock()
        dca_order.order_type = OrderType.LIMIT
        dca_order.side = "buy"
        dca_order.symbol = "BTC/USDT"
        dca_order.quantity = Decimal("0.001")
        dca_order.price = Decimal("60000")
        dca_order.quote_amount = None  # Not a quote-based order

        mock_exchange_connector.place_order.side_effect = APIError("Invalid precision: lot size too small")

        mock_cache = AsyncMock()
        # get_cache is an async function, so patch it as an AsyncMock that returns mock_cache
        with patch("app.core.cache.get_cache", new=AsyncMock(return_value=mock_cache)):
            with pytest.raises(APIError):
                await order_service.submit_order(dca_order)

        mock_cache.invalidate_precision_rules.assert_awaited_once()
        assert dca_order.status == OrderStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_submit_order_generic_precision_error_invalidates_cache(self, order_service, mock_exchange_connector):
        """Test that generic Exception with precision keywords invalidates cache."""
        dca_order = MagicMock()
        dca_order.order_type = OrderType.LIMIT
        dca_order.side = "buy"
        dca_order.symbol = "BTC/USDT"
        dca_order.quantity = Decimal("0.001")
        dca_order.price = Decimal("60000")
        dca_order.quote_amount = None  # Not a quote-based order

        mock_exchange_connector.place_order.side_effect = Exception("Step size validation failed")

        mock_cache = AsyncMock()
        # get_cache is an async function, so patch it as an AsyncMock that returns mock_cache
        with patch("app.core.cache.get_cache", new=AsyncMock(return_value=mock_cache)):
            with pytest.raises(APIError):
                await order_service.submit_order(dca_order)

        mock_cache.invalidate_precision_rules.assert_awaited_once()
        assert dca_order.status == OrderStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_submit_order_non_precision_error_no_cache_invalidation(self, order_service, mock_exchange_connector):
        """Test that non-precision errors don't invalidate cache."""
        dca_order = MagicMock()
        dca_order.order_type = OrderType.LIMIT
        dca_order.side = "buy"
        dca_order.symbol = "BTC/USDT"
        dca_order.quantity = Decimal("0.001")
        dca_order.price = Decimal("60000")

        mock_exchange_connector.place_order.side_effect = APIError("Insufficient balance")

        mock_cache = AsyncMock()
        with patch("app.core.cache.get_cache", return_value=mock_cache):
            with pytest.raises(APIError):
                await order_service.submit_order(dca_order)

        mock_cache.invalidate_precision_rules.assert_not_awaited()


class TestCancelOrderExceptionHandling:
    """Tests for exception handling in cancel_order."""

    @pytest.mark.asyncio
    async def test_cancel_order_api_error(self, order_service, mock_exchange_connector):
        """Test cancel_order with APIError."""
        dca_order = MagicMock()
        dca_order.exchange_order_id = "order_123"
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.cancel_order.side_effect = APIError("Exchange error")

        with pytest.raises(APIError):
            await order_service.cancel_order(dca_order)

        assert dca_order.status == OrderStatus.FAILED.value
        order_service.dca_order_repository.update.assert_awaited()

    @pytest.mark.asyncio
    async def test_cancel_order_generic_exception(self, order_service, mock_exchange_connector):
        """Test cancel_order with generic Exception."""
        dca_order = MagicMock()
        dca_order.exchange_order_id = "order_123"
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.cancel_order.side_effect = Exception("Network error")

        with pytest.raises(APIError):
            await order_service.cancel_order(dca_order)

        assert dca_order.status == OrderStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_cancel_order_order_not_found(self, order_service, mock_exchange_connector):
        """Test cancel_order when order not found on exchange."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.exchange_order_id = "order_123"
        dca_order.symbol = "BTC/USDT"

        # Cancel raises OrderNotFound
        mock_exchange_connector.cancel_order.side_effect = ccxt.OrderNotFound("Order not found")
        # Verification also raises OrderNotFound - order truly doesn't exist
        mock_exchange_connector.get_order_status.side_effect = ccxt.OrderNotFound("Order not found")

        result = await order_service.cancel_order(dca_order)

        # Should still mark as cancelled even if not found
        assert result.status == OrderStatus.CANCELLED.value


class TestPlaceTPOrderEdgeCases:
    """Tests for edge cases in place_tp_order."""

    @pytest.mark.asyncio
    async def test_place_tp_order_tick_size_fetch_fails(self, order_service, mock_exchange_connector):
        """Test place_tp_order when tick_size fetch fails."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.status = OrderStatus.FILLED
        dca_order.tp_order_id = None
        dca_order.side = "BUY"
        dca_order.avg_fill_price = Decimal("60000")
        dca_order.tp_percent = Decimal("1")
        dca_order.tp_price = Decimal("60600")
        dca_order.symbol = "BTC/USDT"
        dca_order.filled_quantity = Decimal("0.001")

        mock_exchange_connector.get_precision_rules.side_effect = Exception("API error")
        mock_exchange_connector.place_order.return_value = {"id": "tp_123"}

        result = await order_service.place_tp_order(dca_order)

        # Should still place order using default tick_size
        assert result.tp_order_id == "tp_123"

    @pytest.mark.asyncio
    async def test_place_tp_order_short_position(self, order_service, mock_exchange_connector):
        """Test place_tp_order for short position (SELL side)."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.status = OrderStatus.FILLED
        dca_order.tp_order_id = None
        dca_order.side = "SELL"  # Short
        dca_order.avg_fill_price = Decimal("60000")
        dca_order.tp_percent = Decimal("1")
        dca_order.tp_price = Decimal("59400")
        dca_order.symbol = "BTC/USDT"
        dca_order.filled_quantity = Decimal("0.001")
        dca_order.price = Decimal("60000")

        mock_exchange_connector.get_precision_rules.return_value = {
            "BTC/USDT": {"tick_size": "0.01"}
        }
        mock_exchange_connector.place_order.return_value = {"id": "tp_short_123"}

        result = await order_service.place_tp_order(dca_order)

        assert result.tp_order_id == "tp_short_123"
        # For short, TP side should be BUY
        call_args = mock_exchange_connector.place_order.call_args
        assert call_args.kwargs.get("side") == "BUY"


class TestPlaceTPOrderForPartialFillEdgeCases:
    """Tests for edge cases in place_tp_order_for_partial_fill."""

    @pytest.mark.asyncio
    async def test_partial_tp_wrong_status(self, order_service, mock_exchange_connector):
        """Test partial TP skips when order is not PARTIALLY_FILLED."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.status = OrderStatus.FILLED  # Wrong status

        result = await order_service.place_tp_order_for_partial_fill(dca_order)

        mock_exchange_connector.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partial_tp_already_has_tp(self, order_service, mock_exchange_connector):
        """Test partial TP skips when TP already exists."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.status = OrderStatus.PARTIALLY_FILLED
        dca_order.tp_order_id = "existing_tp"

        result = await order_service.place_tp_order_for_partial_fill(dca_order)

        mock_exchange_connector.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partial_tp_uses_tp_price_fallback(self, order_service, mock_exchange_connector):
        """Test partial TP uses tp_price when avg_fill_price is not available."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.status = OrderStatus.PARTIALLY_FILLED
        dca_order.tp_order_id = None
        dca_order.filled_quantity = Decimal("0.001")
        dca_order.avg_fill_price = None  # No fill price
        dca_order.tp_percent = Decimal("1")
        dca_order.tp_price = Decimal("60600")
        dca_order.symbol = "BTC/USDT"
        dca_order.side = "BUY"

        mock_exchange_connector.get_precision_rules.return_value = {
            "BTC/USDT": {"tick_size": "0.01"}
        }
        mock_exchange_connector.place_order.return_value = {"id": "tp_fallback"}

        result = await order_service.place_tp_order_for_partial_fill(dca_order)

        assert result.tp_order_id == "tp_fallback"

    @pytest.mark.asyncio
    async def test_partial_tp_exception_handling(self, order_service, mock_exchange_connector):
        """Test partial TP handles exceptions gracefully."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.status = OrderStatus.PARTIALLY_FILLED
        dca_order.tp_order_id = None
        dca_order.filled_quantity = Decimal("0.001")
        dca_order.avg_fill_price = Decimal("60000")
        dca_order.tp_percent = Decimal("1")
        dca_order.symbol = "BTC/USDT"
        dca_order.side = "BUY"

        mock_exchange_connector.get_precision_rules.return_value = {
            "BTC/USDT": {"tick_size": "0.01"}
        }
        mock_exchange_connector.place_order.side_effect = Exception("Network error")

        # Should not raise, just return the order
        result = await order_service.place_tp_order_for_partial_fill(dca_order)

        assert result == dca_order


class TestReconcileOpenOrdersErrors:
    """Tests for error handling in reconcile_open_orders."""

    @pytest.mark.asyncio
    async def test_reconcile_handles_api_error(self, order_service, mock_exchange_connector):
        """Test reconcile_open_orders handles APIError gracefully."""
        order1 = MagicMock()
        order1.id = uuid.uuid4()
        order1.exchange_order_id = "order_1"
        order1.symbol = "BTC/USDT"
        order1.status = OrderStatus.OPEN.value

        order2 = MagicMock()
        order2.id = uuid.uuid4()
        order2.exchange_order_id = "order_2"
        order2.symbol = "ETH/USDT"
        order2.status = OrderStatus.OPEN.value

        order_service.dca_order_repository.get_all_open_orders.return_value = [order1, order2]

        # First order fails, second succeeds
        mock_exchange_connector.get_order_status.side_effect = [
            APIError("Order not found on exchange"),
            {"id": "order_2", "status": "filled", "filled": 0.1, "average": 3000}
        ]

        # Should not raise
        await order_service.reconcile_open_orders()

        # Both orders should be checked
        assert mock_exchange_connector.get_order_status.call_count == 2

    @pytest.mark.asyncio
    async def test_reconcile_handles_unexpected_error(self, order_service, mock_exchange_connector):
        """Test reconcile_open_orders handles unexpected errors gracefully."""
        order1 = MagicMock()
        order1.id = uuid.uuid4()
        order1.exchange_order_id = "order_1"
        order1.symbol = "BTC/USDT"
        order1.status = OrderStatus.OPEN.value

        order_service.dca_order_repository.get_all_open_orders.return_value = [order1]
        mock_exchange_connector.get_order_status.side_effect = Exception("Unexpected error")

        # Should not raise
        await order_service.reconcile_open_orders()


class TestCheckAndRetryStaleTP:
    """Tests for check_and_retry_stale_tp method."""

    @pytest.mark.asyncio
    async def test_stale_tp_no_tp_order(self, order_service, mock_exchange_connector):
        """Test stale TP check when no TP order exists."""
        dca_order = MagicMock()
        dca_order.tp_order_id = None
        dca_order.tp_hit = False

        result = await order_service.check_and_retry_stale_tp(dca_order)

        mock_exchange_connector.get_order_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_already_hit(self, order_service, mock_exchange_connector):
        """Test stale TP check when TP is already hit."""
        dca_order = MagicMock()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = True

        result = await order_service.check_and_retry_stale_tp(dca_order)

        mock_exchange_connector.get_order_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_no_filled_at(self, order_service, mock_exchange_connector):
        """Test stale TP check when filled_at is not set."""
        dca_order = MagicMock()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = False
        dca_order.filled_at = None

        result = await order_service.check_and_retry_stale_tp(dca_order)

        mock_exchange_connector.get_order_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_not_stale_yet(self, order_service, mock_exchange_connector):
        """Test stale TP check when TP is not stale yet."""
        dca_order = MagicMock()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = False
        dca_order.filled_at = datetime.utcnow() - timedelta(hours=12)  # Only 12 hours

        result = await order_service.check_and_retry_stale_tp(dca_order, stale_threshold_hours=24)

        mock_exchange_connector.get_order_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_already_filled_on_exchange(self, order_service, mock_exchange_connector):
        """Test stale TP updates when TP is already filled on exchange."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = False
        dca_order.filled_at = datetime.utcnow() - timedelta(hours=48)  # Stale
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.get_order_status.return_value = {
            "status": "filled"
        }

        result = await order_service.check_and_retry_stale_tp(dca_order)

        assert result.tp_hit is True
        order_service.dca_order_repository.update.assert_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_market_fallback(self, order_service, mock_exchange_connector):
        """Test stale TP uses market fallback when configured."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = False
        dca_order.filled_at = datetime.utcnow() - timedelta(hours=48)
        dca_order.symbol = "BTC/USDT"
        dca_order.side = "BUY"
        dca_order.filled_quantity = Decimal("0.001")

        mock_exchange_connector.get_order_status.return_value = {"status": "open"}
        mock_exchange_connector.cancel_order.return_value = {}
        mock_exchange_connector.place_order.return_value = {"id": "market_tp_123"}

        result = await order_service.check_and_retry_stale_tp(
            dca_order, use_market_fallback=True
        )

        assert result.tp_hit is True
        mock_exchange_connector.place_order.assert_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_cancel_fails(self, order_service, mock_exchange_connector):
        """Test stale TP handles cancel failure gracefully."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = False
        dca_order.filled_at = datetime.utcnow() - timedelta(hours=48)
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.get_order_status.return_value = {"status": "open"}
        mock_exchange_connector.cancel_order.side_effect = Exception("Cancel failed")

        result = await order_service.check_and_retry_stale_tp(dca_order)

        # Should return order without market fallback
        mock_exchange_connector.place_order.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_tp_limit_fallback(self, order_service, mock_exchange_connector):
        """Test stale TP uses limit order when market fallback disabled."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.tp_hit = False
        dca_order.filled_at = datetime.utcnow() - timedelta(hours=48)
        dca_order.symbol = "BTC/USDT"
        dca_order.side = "BUY"
        dca_order.filled_quantity = Decimal("0.001")
        dca_order.avg_fill_price = Decimal("60000")
        dca_order.tp_percent = Decimal("1")
        dca_order.tp_price = Decimal("60600")
        dca_order.status = OrderStatus.FILLED

        mock_exchange_connector.get_order_status.return_value = {"status": "open"}
        mock_exchange_connector.cancel_order.return_value = {}
        mock_exchange_connector.get_precision_rules.return_value = {
            "BTC/USDT": {"tick_size": "0.01"}
        }
        mock_exchange_connector.place_order.return_value = {"id": "new_limit_tp"}

        result = await order_service.check_and_retry_stale_tp(
            dca_order, use_market_fallback=False
        )

        mock_exchange_connector.place_order.assert_awaited()


class TestCheckOrderStatusEdgeCases:
    """Tests for edge cases in check_order_status."""

    @pytest.mark.asyncio
    async def test_check_status_no_exchange_order_id(self, order_service, mock_exchange_connector):
        """Test check_order_status raises when no exchange_order_id."""
        dca_order = MagicMock()
        dca_order.exchange_order_id = None

        with pytest.raises(APIError, match="without an exchange_order_id"):
            await order_service.check_order_status(dca_order)

    @pytest.mark.asyncio
    async def test_check_status_unknown_status(self, order_service, mock_exchange_connector):
        """Test check_order_status handles unknown status."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.exchange_order_id = "order_123"
        dca_order.symbol = "BTC/USDT"
        dca_order.status = OrderStatus.OPEN.value
        dca_order.quantity = Decimal("0.001")
        dca_order.filled_quantity = Decimal("0")
        dca_order.avg_fill_price = None
        dca_order.filled_at = None

        mock_exchange_connector.get_order_status.return_value = {
            "id": "order_123",
            "status": "unknown_status",  # Unknown status
            "filled": 0
        }

        result = await order_service.check_order_status(dca_order)

        # Should keep current status
        assert result.status == OrderStatus.OPEN.value

    @pytest.mark.asyncio
    async def test_check_status_partial_fill_detection(self, order_service, mock_exchange_connector):
        """Test check_order_status detects partial fill from open status."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.exchange_order_id = "order_123"
        dca_order.symbol = "BTC/USDT"
        dca_order.status = OrderStatus.OPEN.value
        dca_order.quantity = Decimal("0.01")
        dca_order.filled_quantity = Decimal("0")
        dca_order.avg_fill_price = None
        dca_order.filled_at = None

        mock_exchange_connector.get_order_status.return_value = {
            "id": "order_123",
            "status": "open",
            "filled": 0.005,  # Partially filled
            "average": 60000
        }

        result = await order_service.check_order_status(dca_order)

        assert result.status == OrderStatus.PARTIALLY_FILLED.value


class TestCancelTPOrderExceptions:
    """Tests for exception handling in cancel_tp_order."""

    @pytest.mark.asyncio
    async def test_cancel_tp_api_error(self, order_service, mock_exchange_connector):
        """Test cancel_tp_order logs APIError but doesn't raise."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.cancel_order.side_effect = APIError("Cancel failed")

        result = await order_service.cancel_tp_order(dca_order)

        # Should still clear TP order ID
        assert result.tp_order_id is None

    @pytest.mark.asyncio
    async def test_cancel_tp_generic_exception(self, order_service, mock_exchange_connector):
        """Test cancel_tp_order logs generic exception but doesn't raise."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.cancel_order.side_effect = Exception("Unexpected")

        result = await order_service.cancel_tp_order(dca_order)

        # Should still clear TP order ID
        assert result.tp_order_id is None


class TestCheckTPStatusErrors:
    """Tests for error handling in check_tp_status."""

    @pytest.mark.asyncio
    async def test_check_tp_status_exception(self, order_service, mock_exchange_connector):
        """Test check_tp_status handles exceptions gracefully."""
        dca_order = MagicMock()
        dca_order.id = uuid.uuid4()
        dca_order.tp_order_id = "tp_123"
        dca_order.symbol = "BTC/USDT"

        mock_exchange_connector.get_order_status.side_effect = Exception("Network error")

        result = await order_service.check_tp_status(dca_order)

        # Should return the order without changes
        assert result == dca_order


class TestPlaceMarketOrderEdgeCases:
    """Tests for edge cases in place_market_order."""

    @pytest.mark.asyncio
    async def test_market_order_slippage_buy(self, order_service, mock_exchange_connector):
        """Test slippage calculation for buy orders."""
        mock_exchange_connector.place_order.return_value = {
            "id": "order_123",
            "status": "closed",
            "filled": 0.001,
            "average": 60600  # 1% above expected
        }

        from app.exceptions import SlippageExceededError

        with pytest.raises(SlippageExceededError):
            await order_service.place_market_order(
                user_id=uuid.uuid4(),
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.001"),
                expected_price=Decimal("60000"),
                max_slippage_percent=0.5,
                slippage_action="reject"
            )

    @pytest.mark.asyncio
    async def test_market_order_exception_handling(self, order_service, mock_exchange_connector):
        """Test market order exception handling."""
        mock_exchange_connector.place_order.side_effect = Exception("Network error")

        with pytest.raises(APIError, match="Failed to place market order"):
            await order_service.place_market_order(
                user_id=uuid.uuid4(),
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.001")
            )
