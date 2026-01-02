"""
Extended tests for OrderFillMonitorService - covering additional edge cases.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from decimal import Decimal
import uuid
from contextlib import asynccontextmanager
import asyncio

from app.services.order_fill_monitor import OrderFillMonitorService
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus


@pytest.fixture
def mock_order_fill_monitor():
    """Create OrderFillMonitorService with mocked dependencies."""
    @asynccontextmanager
    async def mock_session_gen():
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock()
        yield mock_session

    session_factory = MagicMock()
    session_factory.side_effect = mock_session_gen

    service = OrderFillMonitorService(
        session_factory=session_factory,
        dca_order_repository_class=MagicMock(),
        position_group_repository_class=MagicMock(),
        order_service_class=MagicMock(),
        position_manager_service_class=MagicMock(),
        polling_interval_seconds=1
    )
    return service


class TestProcessSingleOrder:
    """Tests for _process_single_order method."""

    @pytest.mark.asyncio
    async def test_process_order_skips_closed_position(self, mock_order_fill_monitor):
        """Test that orders for closed positions are skipped."""
        mock_group = MagicMock()
        mock_group.status = 'closed'

        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTC/USDT"
        )
        order.group = mock_group

        session = AsyncMock()
        session.refresh = AsyncMock()
        semaphore = asyncio.Semaphore(10)

        await mock_order_fill_monitor._process_single_order(
            order=order,
            order_service=AsyncMock(),
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )

        # Should refresh but not process further

    @pytest.mark.asyncio
    async def test_process_order_skips_closing_position(self, mock_order_fill_monitor):
        """Test that orders for closing positions are skipped."""
        mock_group = MagicMock()
        mock_group.status = 'closing'

        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTC/USDT"
        )
        order.group = mock_group

        session = AsyncMock()
        session.refresh = AsyncMock()
        semaphore = asyncio.Semaphore(10)
        order_service = AsyncMock()

        await mock_order_fill_monitor._process_single_order(
            order=order,
            order_service=order_service,
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )

        # check_order_status should not be called for closing positions
        order_service.check_order_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_filled_order_with_tp_hit(self, mock_order_fill_monitor):
        """Test processing a filled order where TP has been hit."""
        mock_group = MagicMock()
        mock_group.status = 'active'
        mock_group.tp_mode = "per_leg"

        mock_pyramid = MagicMock()

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            status=OrderStatus.FILLED.value,
            symbol="BTC/USDT",
            price=Decimal("50000"),
            tp_price=Decimal("52000"),
            filled_quantity=Decimal("0.1"),
            tp_order_id="tp_123",  # TP order already placed, needs status check
            leg_index=0  # Entry order, not TP fill record
        )
        order.group = mock_group
        order.pyramid = mock_pyramid

        updated_order = MagicMock()
        updated_order.tp_hit = True
        updated_order.group = mock_group
        updated_order.pyramid = mock_pyramid
        updated_order.group_id = order.group_id
        updated_order.price = Decimal("50000")
        updated_order.tp_price = Decimal("52000")
        updated_order.filled_quantity = Decimal("0.1")

        order_service = AsyncMock()
        order_service.check_tp_status = AsyncMock(return_value=updated_order)

        position_manager = AsyncMock()
        position_manager.update_position_stats = AsyncMock()

        session = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()
        semaphore = asyncio.Semaphore(10)

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        with patch("app.services.order_fill_monitor.broadcast_tp_hit", new_callable=AsyncMock) as mock_broadcast:
            await mock_order_fill_monitor._process_single_order(
                order=order,
                order_service=order_service,
                position_manager=position_manager,
                connector=AsyncMock(),
                session=session,
                user=mock_user,
                prices_cache={},
                semaphore=semaphore
            )

        order_service.check_tp_status.assert_called_once_with(order)
        position_manager.update_position_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_order_with_partially_filled_status(self, mock_order_fill_monitor):
        """Test processing order that transitions to partially filled."""
        mock_group = MagicMock()
        mock_group.status = 'active'
        mock_group.tp_mode = "per_leg"

        mock_pyramid = MagicMock()

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTC/USDT",
            exchange_order_id="ex123",
            filled_quantity=Decimal("0"),
            quantity=Decimal("1")
        )
        order.group = mock_group
        order.pyramid = mock_pyramid

        # Simulate the order being checked and updated to partially filled
        updated_order = MagicMock()
        updated_order.status = OrderStatus.PARTIALLY_FILLED.value
        updated_order.filled_quantity = Decimal("0.5")
        updated_order.group = mock_group
        updated_order.group_id = order.group_id
        updated_order.pyramid = mock_pyramid
        updated_order.tp_order_id = None

        order_service = AsyncMock()
        order_service.check_order_status = AsyncMock(return_value=updated_order)
        order_service.place_tp_order_for_partial_fill = AsyncMock()

        position_manager = AsyncMock()
        position_manager.update_position_stats = AsyncMock()

        session = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()

        semaphore = asyncio.Semaphore(10)
        mock_user = MagicMock()

        with patch("app.services.order_fill_monitor.broadcast_dca_fill", new_callable=AsyncMock):
            await mock_order_fill_monitor._process_single_order(
                order=order,
                order_service=order_service,
                position_manager=position_manager,
                connector=AsyncMock(),
                session=session,
                user=mock_user,
                prices_cache={},
                semaphore=semaphore
            )

        order_service.check_order_status.assert_called_once_with(order)
        # Should update position stats for partial fill
        position_manager.update_position_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_order_handles_deadlock(self, mock_order_fill_monitor):
        """Test that deadlock errors are handled gracefully."""
        mock_group = MagicMock()
        mock_group.status = 'active'

        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTC/USDT"
        )
        order.group = mock_group

        session = AsyncMock()
        session.refresh = AsyncMock(side_effect=Exception("deadlock detected"))
        semaphore = asyncio.Semaphore(10)

        # Should not raise, just log warning
        await mock_order_fill_monitor._process_single_order(
            order=order,
            order_service=AsyncMock(),
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )


class TestDCABeyondThreshold:
    """Tests for _check_dca_beyond_threshold method."""

    @pytest.mark.asyncio
    async def test_check_dca_beyond_threshold_no_group(self, mock_order_fill_monitor):
        """Test early return when order has no group."""
        order = DCAOrder(id=uuid.uuid4(), status=OrderStatus.OPEN.value)
        order.group = None

        # Should not raise
        await mock_order_fill_monitor._check_dca_beyond_threshold(
            order=order,
            current_price=Decimal("50000"),
            order_service=AsyncMock(),
            session=AsyncMock()
        )

    @pytest.mark.asyncio
    async def test_check_dca_beyond_threshold_long_cancelled(self, mock_order_fill_monitor):
        """Test DCA order cancelled when price moves beyond threshold for long position."""
        mock_group = MagicMock()
        mock_group.user_id = uuid.uuid4()
        mock_group.symbol = "BTCUSDT"
        mock_group.timeframe = 60
        mock_group.exchange = "binance"
        mock_group.side = "long"
        mock_group.weighted_avg_entry = Decimal("50000")

        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTCUSDT"
        )
        order.group = mock_group

        # Price dropped 10% (beyond 5% threshold)
        current_price = Decimal("45000")

        mock_config = MagicMock()
        mock_config.cancel_dca_beyond_percent = 5.0

        session = AsyncMock()
        order_service = AsyncMock()
        order_service.cancel_order = AsyncMock()

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_specific_config = AsyncMock(return_value=mock_config)
            mock_repo_cls.return_value = mock_repo

            await mock_order_fill_monitor._check_dca_beyond_threshold(
                order=order,
                current_price=current_price,
                order_service=order_service,
                session=session
            )

        order_service.cancel_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_check_dca_beyond_threshold_no_config(self, mock_order_fill_monitor):
        """Test no cancellation when no config exists."""
        mock_group = MagicMock()
        mock_group.user_id = uuid.uuid4()
        mock_group.symbol = "BTCUSDT"
        mock_group.timeframe = 60
        mock_group.exchange = "binance"

        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTCUSDT"
        )
        order.group = mock_group

        session = AsyncMock()
        order_service = AsyncMock()
        order_service.cancel_order = AsyncMock()

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_specific_config = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            await mock_order_fill_monitor._check_dca_beyond_threshold(
                order=order,
                current_price=Decimal("50000"),
                order_service=order_service,
                session=session
            )

        order_service.cancel_order.assert_not_called()


class TestFetchAllPrices:
    """Tests for _fetch_all_prices method."""

    @pytest.mark.asyncio
    async def test_fetch_all_prices_success(self, mock_order_fill_monitor):
        """Test successful batch price fetching."""
        connector = AsyncMock()
        connector.get_all_tickers = AsyncMock(return_value={
            "BTCUSDT": {"last": "50000.0"},
            "ETHUSDT": {"last": "3000.0"}
        })

        symbols = ["BTCUSDT", "ETHUSDT"]
        prices = await mock_order_fill_monitor._fetch_all_prices(connector, symbols)

        assert "BTCUSDT" in prices
        assert "ETHUSDT" in prices
        assert prices["BTCUSDT"] == Decimal("50000.0")
        assert prices["ETHUSDT"] == Decimal("3000.0")

    @pytest.mark.asyncio
    async def test_fetch_all_prices_with_slash_symbol(self, mock_order_fill_monitor):
        """Test fetching prices for symbols with slash notation."""
        connector = AsyncMock()
        connector.get_all_tickers = AsyncMock(return_value={
            "BTCUSDT": {"last": "50000.0"}  # Exchange returns without slash
        })

        symbols = ["BTC/USDT"]  # Symbol has slash
        prices = await mock_order_fill_monitor._fetch_all_prices(connector, symbols)

        # Should find the price using the non-slash version
        assert "BTC/USDT" in prices

    @pytest.mark.asyncio
    async def test_fetch_all_prices_exception(self, mock_order_fill_monitor):
        """Test handling exceptions during price fetch."""
        connector = AsyncMock()
        connector.get_all_tickers = AsyncMock(side_effect=Exception("API error"))

        symbols = ["BTCUSDT"]
        prices = await mock_order_fill_monitor._fetch_all_prices(connector, symbols)

        # Should return empty dict on error
        assert prices == {}


class TestMonitoringLoop:
    """Tests for monitoring loop behavior."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_cancelled(self, mock_order_fill_monitor):
        """Test monitoring loop handles cancellation."""
        mock_order_fill_monitor._check_orders = AsyncMock()
        mock_order_fill_monitor._report_health = AsyncMock()
        mock_order_fill_monitor.polling_interval_seconds = 0.01
        mock_order_fill_monitor._running = True

        # Start the loop and cancel it
        task = asyncio.create_task(mock_order_fill_monitor._monitoring_loop())
        await asyncio.sleep(0.03)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Health should be reported
        assert mock_order_fill_monitor._check_orders.call_count >= 1


class TestReportHealth:
    """Tests for _report_health method."""

    @pytest.mark.asyncio
    async def test_report_health_success(self, mock_order_fill_monitor):
        """Test successful health reporting."""
        with patch("app.core.cache.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.update_service_health = AsyncMock(return_value=True)
            mock_get_cache.return_value = mock_cache

            await mock_order_fill_monitor._report_health("running", {"cycle_count": 5})

            mock_cache.update_service_health.assert_called_once_with(
                "order_fill_monitor",
                "running",
                {"cycle_count": 5}
            )

    @pytest.mark.asyncio
    async def test_report_health_exception(self, mock_order_fill_monitor):
        """Test health reporting handles exceptions."""
        with patch("app.core.cache.get_cache") as mock_get_cache:
            mock_get_cache.side_effect = Exception("Cache error")

            # Should not raise
            await mock_order_fill_monitor._report_health("running")


class TestStopMonitoringTask:
    """Tests for stop_monitoring_task method."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_order_fill_monitor):
        """Test stopping when not running."""
        mock_order_fill_monitor._running = False
        mock_order_fill_monitor._monitor_task = None

        # Should not raise
        await mock_order_fill_monitor.stop_monitoring_task()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, mock_order_fill_monitor):
        """Test that stop cancels the running task."""
        mock_order_fill_monitor._check_orders = AsyncMock()
        mock_order_fill_monitor._report_health = AsyncMock()
        mock_order_fill_monitor.polling_interval_seconds = 0.5

        await mock_order_fill_monitor.start_monitoring_task()
        assert mock_order_fill_monitor._running is True

        await mock_order_fill_monitor.stop_monitoring_task()
        assert mock_order_fill_monitor._running is False


class TestAggregateTPForIdlePositions:
    """Tests for _check_aggregate_tp_for_idle_positions method."""

    @pytest.mark.asyncio
    async def test_check_aggregate_tp_no_positions(self, mock_order_fill_monitor):
        """Test early return when no positions found."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        user = MagicMock()
        user.id = uuid.uuid4()

        await mock_order_fill_monitor._check_aggregate_tp_for_idle_positions(session, user)

        # Should not raise or try to process positions

    @pytest.mark.asyncio
    async def test_check_aggregate_tp_skips_positions_with_open_orders(self, mock_order_fill_monitor):
        """Test that positions with open orders are skipped."""
        session = AsyncMock()

        # Create position with open orders
        open_order = MagicMock()
        open_order.status = OrderStatus.OPEN.value

        position = MagicMock()
        position.id = uuid.uuid4()
        position.exchange = "binance"
        position.dca_orders = [open_order]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {"binance": {"encrypted_data": "mock"}}

        mock_order_fill_monitor.encryption_service = MagicMock()
        mock_order_fill_monitor.encryption_service.decrypt_keys.return_value = ("api", "secret")

        await mock_order_fill_monitor._check_aggregate_tp_for_idle_positions(session, user)

        # Position with open orders should be skipped


class TestCheckSinglePositionAggregateTP:
    """Tests for _check_single_position_aggregate_tp method."""

    @pytest.mark.asyncio
    async def test_aggregate_tp_triggered_long(self, mock_order_fill_monitor):
        """Test aggregate TP execution for long position."""
        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("2")  # 2% TP
        position.exchange = "binance"
        position.total_hedged_value_usd = Decimal("0")
        position.total_hedged_qty = Decimal("0")

        # Current price above TP level
        current_price = Decimal("51500")  # 3% above entry, triggers 2% TP

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=current_price)

        order_service = AsyncMock()
        order_service.cancel_open_orders_for_group = AsyncMock()
        order_service.place_market_order = AsyncMock()

        mock_order_fill_monitor.order_service_class.return_value = order_service

        position_repo = AsyncMock()
        position_repo.update = AsyncMock()

        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        with patch("app.services.order_fill_monitor.broadcast_tp_hit", new_callable=AsyncMock):
            await mock_order_fill_monitor._check_single_position_aggregate_tp(
                session=session,
                user=user,
                position_group=position,
                connector=connector,
                position_group_repo=position_repo
            )

        order_service.cancel_open_orders_for_group.assert_called_once_with(position.id)
        order_service.place_market_order.assert_called_once()
        position_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregate_tp_not_triggered(self, mock_order_fill_monitor):
        """Test aggregate TP not executed when below target."""
        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("5")  # 5% TP target

        # Current price below TP level
        current_price = Decimal("51000")  # Only 2% above entry

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=current_price)

        position_repo = AsyncMock()

        session = AsyncMock()
        user = MagicMock()

        await mock_order_fill_monitor._check_single_position_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )

        # Should not update position
        position_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_aggregate_tp_zero_quantity_skipped(self, mock_order_fill_monitor):
        """Test that positions with zero quantity are skipped."""
        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0")  # Zero quantity

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=Decimal("55000"))

        position_repo = AsyncMock()
        session = AsyncMock()
        user = MagicMock()

        await mock_order_fill_monitor._check_single_position_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )

        position_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_aggregate_tp_handles_exception(self, mock_order_fill_monitor):
        """Test that exceptions are handled gracefully."""
        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(side_effect=Exception("API error"))

        position_repo = AsyncMock()
        session = AsyncMock()
        user = MagicMock()

        # Should not raise
        await mock_order_fill_monitor._check_single_position_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )


class TestEncryptionServiceInit:
    """Tests for encryption service initialization."""

    def test_encryption_service_init_failure(self):
        """Test handling encryption service init failure."""
        with patch("app.services.order_fill_monitor.EncryptionService") as mock_enc:
            mock_enc.side_effect = Exception("Key not found")

            service = OrderFillMonitorService(
                session_factory=MagicMock(),
                dca_order_repository_class=MagicMock(),
                position_group_repository_class=MagicMock(),
                order_service_class=MagicMock(),
                position_manager_service_class=MagicMock(),
            )

            assert service.encryption_service is None
