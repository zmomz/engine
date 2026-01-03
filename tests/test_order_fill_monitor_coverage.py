"""
Additional tests for OrderFillMonitorService to improve coverage.
Focuses on uncovered code paths: per-leg TP completion, pyramid aggregate TP,
short positions, and edge cases.
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
from app.models.pyramid import Pyramid, PyramidStatus


@pytest.fixture
def mock_monitor_service():
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


class TestCheckPerLegPositionsAllTPsHit:
    """Tests for _check_per_leg_positions_all_tps_hit method."""

    @pytest.mark.asyncio
    async def test_closes_position_when_all_tps_hit(self, mock_monitor_service):
        """Test position is closed when all per-leg TPs are hit."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        # Create filled entry orders with tp_hit=True
        filled_order1 = MagicMock()
        filled_order1.leg_index = 0
        filled_order1.status = OrderStatus.FILLED.value
        filled_order1.tp_hit = True

        filled_order2 = MagicMock()
        filled_order2.leg_index = 1
        filled_order2.status = OrderStatus.FILLED.value
        filled_order2.tp_hit = True

        position = MagicMock()
        position.id = uuid.uuid4()
        position.status = PositionGroupStatus.ACTIVE.value
        position.tp_mode = "per_leg"
        position.dca_orders = [filled_order1, filled_order2]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        position_repo = AsyncMock()
        position_repo.update = AsyncMock()
        mock_monitor_service.position_group_repository_class.return_value = position_repo

        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

        # Position should be closed
        assert position.status == PositionGroupStatus.CLOSED

    @pytest.mark.asyncio
    async def test_does_not_close_position_with_pending_orders(self, mock_monitor_service):
        """Test position not closed when there are pending orders."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        filled_order = MagicMock()
        filled_order.leg_index = 0
        filled_order.status = OrderStatus.FILLED.value
        filled_order.tp_hit = True

        pending_order = MagicMock()
        pending_order.leg_index = 1
        pending_order.status = OrderStatus.OPEN.value

        position = MagicMock()
        position.id = uuid.uuid4()
        position.status = PositionGroupStatus.ACTIVE.value
        position.tp_mode = "per_leg"
        position.dca_orders = [filled_order, pending_order]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        position_repo = AsyncMock()
        mock_monitor_service.position_group_repository_class.return_value = position_repo

        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

        # Position should not be closed
        assert position.status == PositionGroupStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_does_not_close_position_with_tp_not_hit(self, mock_monitor_service):
        """Test position not closed when some TPs haven't hit."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        filled_order1 = MagicMock()
        filled_order1.leg_index = 0
        filled_order1.status = OrderStatus.FILLED.value
        filled_order1.tp_hit = True

        filled_order2 = MagicMock()
        filled_order2.leg_index = 1
        filled_order2.status = OrderStatus.FILLED.value
        filled_order2.tp_hit = False  # TP not hit yet

        position = MagicMock()
        position.id = uuid.uuid4()
        position.status = PositionGroupStatus.ACTIVE.value
        position.tp_mode = "per_leg"
        position.dca_orders = [filled_order1, filled_order2]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

        # Position should not be closed
        assert position.status == PositionGroupStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_skips_positions_with_no_filled_entries(self, mock_monitor_service):
        """Test positions with no filled entries are skipped."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        pending_order = MagicMock()
        pending_order.leg_index = 0
        pending_order.status = OrderStatus.TRIGGER_PENDING.value

        position = MagicMock()
        position.id = uuid.uuid4()
        position.status = PositionGroupStatus.ACTIVE.value
        position.tp_mode = "per_leg"
        position.dca_orders = [pending_order]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

        # Position should not be modified
        assert position.status == PositionGroupStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, mock_monitor_service):
        """Test exception handling in per-leg TP check."""
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("Database error"))
        user = MagicMock()
        user.id = uuid.uuid4()

        # Should not raise
        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

    @pytest.mark.asyncio
    async def test_no_positions_returns_early(self, mock_monitor_service):
        """Test early return when no positions found."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

        # No errors, should return early

    @pytest.mark.asyncio
    async def test_hybrid_mode_positions_included(self, mock_monitor_service):
        """Test that hybrid mode positions are also checked."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        filled_order = MagicMock()
        filled_order.leg_index = 0
        filled_order.status = OrderStatus.FILLED.value
        filled_order.tp_hit = True

        position = MagicMock()
        position.id = uuid.uuid4()
        position.status = PositionGroupStatus.ACTIVE.value
        position.tp_mode = "hybrid"  # Hybrid mode
        position.dca_orders = [filled_order]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        position_repo = AsyncMock()
        position_repo.update = AsyncMock()
        mock_monitor_service.position_group_repository_class.return_value = position_repo

        await mock_monitor_service._check_per_leg_positions_all_tps_hit(session, user)

        # Position should be closed (all TPs hit, no pending orders)
        assert position.status == PositionGroupStatus.CLOSED


class TestCheckPyramidAggregateTPForIdlePositions:
    """Tests for _check_pyramid_aggregate_tp_for_idle_positions method."""

    @pytest.mark.asyncio
    async def test_no_positions_returns_early(self, mock_monitor_service):
        """Test early return when no pyramid_aggregate positions found."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await mock_monitor_service._check_pyramid_aggregate_tp_for_idle_positions(session, user)

    @pytest.mark.asyncio
    async def test_processes_positions_by_exchange(self, mock_monitor_service):
        """Test positions are grouped and processed by exchange."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {"mock": {"api_key": "test"}}

        position = MagicMock()
        position.id = uuid.uuid4()
        position.exchange = "mock"
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("2")
        position.dca_orders = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        mock_connector = AsyncMock()
        mock_connector.get_current_price = AsyncMock(return_value=Decimal("50500"))
        mock_connector.close = AsyncMock()

        with patch("app.services.order_fill_monitor.get_exchange_connector", return_value=mock_connector):
            await mock_monitor_service._check_pyramid_aggregate_tp_for_idle_positions(session, user)

        mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_exchange_without_keys(self, mock_monitor_service):
        """Test skipping exchanges user doesn't have keys for."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {}  # No keys

        position = MagicMock()
        position.id = uuid.uuid4()
        position.exchange = "binance"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        await mock_monitor_service._check_pyramid_aggregate_tp_for_idle_positions(session, user)

        # Should complete without error

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, mock_monitor_service):
        """Test exception handling."""
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        user = MagicMock()
        user.id = uuid.uuid4()

        # Should not raise
        await mock_monitor_service._check_pyramid_aggregate_tp_for_idle_positions(session, user)


class TestCheckSinglePositionPyramidAggregateTP:
    """Tests for _check_single_position_pyramid_aggregate_tp method."""

    @pytest.mark.asyncio
    async def test_executes_tp_for_pyramid_above_target(self, mock_monitor_service):
        """Test pyramid TP execution when price exceeds target."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        # Create pyramid with filled orders
        pyramid = MagicMock()
        pyramid.id = uuid.uuid4()
        pyramid.pyramid_index = 0

        filled_order = MagicMock()
        filled_order.pyramid_id = pyramid.id
        filled_order.status = OrderStatus.FILLED.value
        filled_order.leg_index = 0
        filled_order.tp_hit = False
        filled_order.filled_quantity = Decimal("0.1")
        filled_order.quantity = Decimal("0.1")
        filled_order.avg_fill_price = Decimal("50000")
        filled_order.price = Decimal("50000")

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.exchange = "mock"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("2")
        position.dca_orders = [filled_order]
        position.realized_pnl_usd = Decimal("0")
        position.total_exit_fees_usd = Decimal("0")

        # Mock pyramid query result
        pyramid_result = MagicMock()
        pyramid_result.scalars.return_value.all.return_value = [pyramid]
        session.execute = AsyncMock(return_value=pyramid_result)

        # Current price 3% above entry (triggers 2% TP)
        current_price = Decimal("51500")
        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=current_price)

        order_service = AsyncMock()
        order_service.place_market_order = AsyncMock(return_value={
            "avgPrice": "51500",
            "cumulative_fee": "0.5"
        })
        order_service.cancel_open_orders_for_group = AsyncMock()
        mock_monitor_service.order_service_class.return_value = order_service

        position_repo = AsyncMock()
        position_repo.update = AsyncMock()

        with patch("app.services.order_fill_monitor.broadcast_tp_hit", new_callable=AsyncMock):
            await mock_monitor_service._check_single_position_pyramid_aggregate_tp(
                session=session,
                user=user,
                position_group=position,
                connector=connector,
                position_group_repo=position_repo
            )

        order_service.place_market_order.assert_called_once()
        assert filled_order.tp_hit is True

    @pytest.mark.asyncio
    async def test_closes_position_when_all_pyramids_done(self, mock_monitor_service):
        """Test position closes when all pyramids have TP executed."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        pyramid = MagicMock()
        pyramid.id = uuid.uuid4()
        pyramid.pyramid_index = 0

        filled_order = MagicMock()
        filled_order.pyramid_id = pyramid.id
        filled_order.status = OrderStatus.FILLED.value
        filled_order.leg_index = 0
        filled_order.tp_hit = False
        filled_order.filled_quantity = Decimal("0.1")
        filled_order.quantity = Decimal("0.1")
        filled_order.avg_fill_price = Decimal("50000")
        filled_order.price = Decimal("50000")

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.exchange = "mock"
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("2")
        position.dca_orders = [filled_order]
        position.realized_pnl_usd = Decimal("0")
        position.total_exit_fees_usd = Decimal("0")

        pyramid_result = MagicMock()
        pyramid_result.scalars.return_value.all.return_value = [pyramid]
        session.execute = AsyncMock(return_value=pyramid_result)

        current_price = Decimal("51500")
        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=current_price)

        order_service = AsyncMock()
        order_service.place_market_order = AsyncMock(return_value={
            "avgPrice": "51500",
            "fee": "0.5"
        })
        order_service.cancel_open_orders_for_group = AsyncMock()
        mock_monitor_service.order_service_class.return_value = order_service

        position_repo = AsyncMock()
        position_repo.update = AsyncMock()

        with patch("app.services.order_fill_monitor.broadcast_tp_hit", new_callable=AsyncMock):
            await mock_monitor_service._check_single_position_pyramid_aggregate_tp(
                session=session,
                user=user,
                position_group=position,
                connector=connector,
                position_group_repo=position_repo
            )

        # Position quantity reduced to 0, should be closed
        assert position.status == PositionGroupStatus.CLOSED
        order_service.cancel_open_orders_for_group.assert_called()

    @pytest.mark.asyncio
    async def test_skips_pyramid_with_no_filled_orders(self, mock_monitor_service):
        """Test pyramid with no filled orders is skipped."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        pyramid = MagicMock()
        pyramid.id = uuid.uuid4()
        pyramid.pyramid_index = 0

        # No orders for this pyramid
        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.total_filled_quantity = Decimal("0")
        position.tp_aggregate_percent = Decimal("2")
        position.dca_orders = []  # No orders

        pyramid_result = MagicMock()
        pyramid_result.scalars.return_value.all.return_value = [pyramid]
        session.execute = AsyncMock(return_value=pyramid_result)

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=Decimal("51500"))

        position_repo = AsyncMock()

        await mock_monitor_service._check_single_position_pyramid_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )

        # No update should happen
        position_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_pyramid_with_all_tps_already_hit(self, mock_monitor_service):
        """Test pyramid with all TPs already hit is skipped."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        pyramid = MagicMock()
        pyramid.id = uuid.uuid4()

        filled_order = MagicMock()
        filled_order.pyramid_id = pyramid.id
        filled_order.status = OrderStatus.FILLED.value
        filled_order.leg_index = 0
        filled_order.tp_hit = True  # Already hit

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("2")
        position.dca_orders = [filled_order]

        pyramid_result = MagicMock()
        pyramid_result.scalars.return_value.all.return_value = [pyramid]
        session.execute = AsyncMock(return_value=pyramid_result)

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=Decimal("55000"))

        position_repo = AsyncMock()

        await mock_monitor_service._check_single_position_pyramid_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )

        # No market order should be placed
        mock_monitor_service.order_service_class.return_value.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_trigger_below_target(self, mock_monitor_service):
        """Test TP is not triggered when price is below target."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        pyramid = MagicMock()
        pyramid.id = uuid.uuid4()

        filled_order = MagicMock()
        filled_order.pyramid_id = pyramid.id
        filled_order.status = OrderStatus.FILLED.value
        filled_order.leg_index = 0
        filled_order.tp_hit = False
        filled_order.filled_quantity = Decimal("0.1")
        filled_order.quantity = Decimal("0.1")
        filled_order.avg_fill_price = Decimal("50000")
        filled_order.price = Decimal("50000")

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("5")  # 5% target
        position.dca_orders = [filled_order]

        pyramid_result = MagicMock()
        pyramid_result.scalars.return_value.all.return_value = [pyramid]
        session.execute = AsyncMock(return_value=pyramid_result)

        # Price only 2% above entry
        connector = AsyncMock()
        connector.get_current_price = AsyncMock(return_value=Decimal("51000"))

        order_service = AsyncMock()
        order_service.place_market_order = AsyncMock()
        mock_monitor_service.order_service_class.return_value = order_service

        position_repo = AsyncMock()

        await mock_monitor_service._check_single_position_pyramid_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )

        # Market order should NOT be placed since TP wasn't triggered
        order_service.place_market_order.assert_not_called()
        # But position status should NOT have changed to CLOSED
        assert position.status != PositionGroupStatus.CLOSED

    @pytest.mark.asyncio
    async def test_handles_exception(self, mock_monitor_service):
        """Test exception handling."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()

        position = MagicMock()
        position.id = uuid.uuid4()
        position.symbol = "BTCUSDT"

        connector = AsyncMock()
        connector.get_current_price = AsyncMock(side_effect=Exception("API error"))

        position_repo = AsyncMock()

        # Should not raise
        await mock_monitor_service._check_single_position_pyramid_aggregate_tp(
            session=session,
            user=user,
            position_group=position,
            connector=connector,
            position_group_repo=position_repo
        )


class TestProcessSingleOrderEdgeCases:
    """Tests for edge cases in _process_single_order."""

    @pytest.mark.asyncio
    async def test_filled_order_places_missing_tp_order(self, mock_monitor_service):
        """Test that filled orders with missing TP get TP placed."""
        mock_group = MagicMock()
        mock_group.status = 'active'
        mock_group.tp_mode = "per_leg"

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            status=OrderStatus.FILLED.value,
            symbol="BTC/USDT",
            tp_order_id=None,  # Missing TP order
            leg_index=0
        )
        order.group = mock_group
        order.pyramid = None

        session = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()

        order_service = AsyncMock()
        order_service.place_tp_order = AsyncMock()

        semaphore = asyncio.Semaphore(10)

        await mock_monitor_service._process_single_order(
            order=order,
            order_service=order_service,
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )

        # Should place the missing TP order
        order_service.place_tp_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_skips_tp_fill_record(self, mock_monitor_service):
        """Test that TP fill records (leg_index=999) are skipped."""
        mock_group = MagicMock()
        mock_group.status = 'active'
        mock_group.tp_mode = "per_leg"

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            status=OrderStatus.FILLED.value,
            symbol="BTC/USDT",
            leg_index=999  # TP fill record
        )
        order.group = mock_group
        order.pyramid = None

        session = AsyncMock()
        session.refresh = AsyncMock()

        order_service = AsyncMock()
        order_service.check_tp_status = AsyncMock()
        order_service.place_tp_order = AsyncMock()

        semaphore = asyncio.Semaphore(10)

        await mock_monitor_service._process_single_order(
            order=order,
            order_service=order_service,
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )

        # Should not check TP status or place TP for TP fill record
        order_service.check_tp_status.assert_not_called()
        order_service.place_tp_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_filled_order_skips_tp_for_aggregate_mode(self, mock_monitor_service):
        """Test that filled orders in aggregate mode don't place per-leg TP."""
        mock_group = MagicMock()
        mock_group.status = 'active'
        mock_group.tp_mode = "aggregate"  # Not per_leg

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            status=OrderStatus.FILLED.value,
            symbol="BTC/USDT",
            tp_order_id=None,
            leg_index=0
        )
        order.group = mock_group
        order.pyramid = None

        session = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()

        order_service = AsyncMock()
        order_service.place_tp_order = AsyncMock()

        semaphore = asyncio.Semaphore(10)

        await mock_monitor_service._process_single_order(
            order=order,
            order_service=order_service,
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )

        # Should not place TP for aggregate mode
        order_service.place_tp_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_refresh_exception(self, mock_monitor_service):
        """Test handling of refresh exception."""
        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTC/USDT"
        )
        order.group = MagicMock()

        session = AsyncMock()
        session.refresh = AsyncMock(side_effect=Exception("Session error"))

        semaphore = asyncio.Semaphore(10)

        # Should not raise
        await mock_monitor_service._process_single_order(
            order=order,
            order_service=AsyncMock(),
            position_manager=AsyncMock(),
            connector=AsyncMock(),
            session=session,
            user=MagicMock(),
            prices_cache={},
            semaphore=semaphore
        )

    @pytest.mark.asyncio
    async def test_uses_prices_cache(self, mock_monitor_service):
        """Test that prices_cache is used for trigger pending orders."""
        mock_group = MagicMock()
        mock_group.status = 'active'
        mock_group.side = 'long'
        mock_group.weighted_avg_entry = Decimal("50000")

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            status=OrderStatus.TRIGGER_PENDING.value,
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            price=Decimal("49000"),  # Below cache price
            gap_percent=Decimal("-2"),
            leg_index=1
        )
        order.group = mock_group
        order.pyramid = None

        session = AsyncMock()
        session.refresh = AsyncMock()

        order_service = AsyncMock()
        order_service.submit_order = AsyncMock()

        connector = AsyncMock()
        connector.get_current_price = AsyncMock()  # Should not be called

        semaphore = asyncio.Semaphore(10)

        # Provide price in cache
        prices_cache = {"BTC/USDT": Decimal("48000")}  # Below trigger price

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_specific_config = AsyncMock(return_value=None)
            mock_repo.return_value = mock_repo_instance

            await mock_monitor_service._process_single_order(
                order=order,
                order_service=order_service,
                position_manager=AsyncMock(),
                connector=connector,
                session=session,
                user=MagicMock(),
                prices_cache=prices_cache,
                semaphore=semaphore
            )

        # Submit order should be called since price is below trigger
        order_service.submit_order.assert_called_once_with(order)


class TestDCABeyondThresholdSymbolNormalization:
    """Tests for symbol normalization in DCA beyond threshold check."""

    @pytest.mark.asyncio
    async def test_normalizes_symbol_with_slash(self, mock_monitor_service):
        """Test symbol normalization when symbol has no slash."""
        mock_group = MagicMock()
        mock_group.user_id = uuid.uuid4()
        mock_group.symbol = "ETHUSDT"  # No slash
        mock_group.timeframe = 60
        mock_group.exchange = "binance"
        mock_group.side = "long"
        mock_group.weighted_avg_entry = Decimal("3000")

        order = MagicMock()
        order.id = uuid.uuid4()
        order.status = OrderStatus.OPEN.value
        order.group = mock_group

        mock_config = MagicMock()
        mock_config.cancel_dca_beyond_percent = Decimal("5")

        session = AsyncMock()
        order_service = AsyncMock()

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_specific_config = AsyncMock(return_value=mock_config)
            mock_repo.return_value = mock_repo_instance

            await mock_monitor_service._check_dca_beyond_threshold(
                order=order,
                current_price=Decimal("3100"),  # Within threshold
                order_service=order_service,
                session=session
            )

            # Verify normalized pair was used
            call_args = mock_repo_instance.get_specific_config.call_args
            assert call_args[1]["pair"] == "ETH/USDT"

    @pytest.mark.asyncio
    async def test_handles_usd_suffix(self, mock_monitor_service):
        """Test symbol normalization for USD suffix."""
        mock_group = MagicMock()
        mock_group.user_id = uuid.uuid4()
        mock_group.symbol = "BTCUSD"  # USD suffix
        mock_group.timeframe = 60
        mock_group.exchange = "binance"
        mock_group.side = "long"
        mock_group.weighted_avg_entry = Decimal("50000")

        order = MagicMock()
        order.id = uuid.uuid4()
        order.status = OrderStatus.OPEN.value
        order.group = mock_group

        session = AsyncMock()
        order_service = AsyncMock()

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_specific_config = AsyncMock(return_value=None)
            mock_repo.return_value = mock_repo_instance

            await mock_monitor_service._check_dca_beyond_threshold(
                order=order,
                current_price=Decimal("50000"),
                order_service=order_service,
                session=session
            )

            call_args = mock_repo_instance.get_specific_config.call_args
            assert call_args[1]["pair"] == "BTC/USD"

    @pytest.mark.asyncio
    async def test_config_as_dict_with_threshold(self, mock_monitor_service):
        """Test handling config returned as dict instead of object."""
        mock_group = MagicMock()
        mock_group.user_id = uuid.uuid4()
        mock_group.symbol = "BTC/USDT"
        mock_group.timeframe = 60
        mock_group.exchange = "binance"
        mock_group.side = "long"
        mock_group.weighted_avg_entry = Decimal("50000")

        order = MagicMock()
        order.id = uuid.uuid4()
        order.status = OrderStatus.OPEN.value
        order.group = mock_group

        # Config as dict
        mock_config = {"cancel_dca_beyond_percent": 5}

        session = AsyncMock()
        order_service = AsyncMock()
        order_service.cancel_order = AsyncMock()

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_specific_config = AsyncMock(return_value=mock_config)
            mock_repo.return_value = mock_repo_instance

            # Price dropped 10%
            await mock_monitor_service._check_dca_beyond_threshold(
                order=order,
                current_price=Decimal("45000"),
                order_service=order_service,
                session=session
            )

        order_service.cancel_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_zero_entry_price_skipped(self, mock_monitor_service):
        """Test that positions with zero entry price are skipped."""
        mock_group = MagicMock()
        mock_group.user_id = uuid.uuid4()
        mock_group.symbol = "BTC/USDT"
        mock_group.timeframe = 60
        mock_group.exchange = "binance"
        mock_group.side = "long"
        mock_group.weighted_avg_entry = Decimal("0")  # Zero entry

        order = MagicMock()
        order.id = uuid.uuid4()
        order.status = OrderStatus.OPEN.value
        order.group = mock_group

        mock_config = MagicMock()
        mock_config.cancel_dca_beyond_percent = Decimal("5")

        session = AsyncMock()
        order_service = AsyncMock()

        with patch("app.services.order_fill_monitor.DCAConfigurationRepository") as mock_repo:
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_specific_config = AsyncMock(return_value=mock_config)
            mock_repo.return_value = mock_repo_instance

            await mock_monitor_service._check_dca_beyond_threshold(
                order=order,
                current_price=Decimal("10000"),
                order_service=order_service,
                session=session
            )

        # Should not cancel due to zero entry price
        order_service.cancel_order.assert_not_called()


class TestCheckOrdersMockExchange:
    """Tests for mock exchange handling in _check_orders."""

    @pytest.mark.asyncio
    async def test_mock_exchange_uses_mock_keys(self, mock_monitor_service):
        """Test that mock exchange uses predefined mock keys."""
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.username = "testuser"
        mock_user.encrypted_api_keys = {"mock": {}}  # Has mock exchange

        mock_group = MagicMock()
        mock_group.exchange = "mock"
        mock_group.status = "active"

        order = DCAOrder(
            id=uuid.uuid4(),
            status=OrderStatus.OPEN.value,
            symbol="BTC/USDT"
        )
        order.group = mock_group
        order.pyramid = None

        mock_monitor_service.encryption_service = MagicMock()
        mock_monitor_service.dca_order_repository_class.return_value.get_all_open_orders_for_all_users = AsyncMock(
            return_value={str(mock_user.id): [order]}
        )

        mock_connector = AsyncMock()
        mock_connector.close = AsyncMock()
        mock_connector.get_all_tickers = AsyncMock(return_value={})

        mock_order_service = AsyncMock()
        mock_order_service.check_order_status = AsyncMock(return_value=order)
        mock_monitor_service.order_service_class.return_value = mock_order_service

        with patch("app.services.order_fill_monitor.UserRepository") as mock_user_repo:
            mock_user_repo.return_value.get_all_active_users = AsyncMock(return_value=[mock_user])

            with patch("app.services.order_fill_monitor.get_exchange_connector", return_value=mock_connector) as mock_get_conn:
                await mock_monitor_service._check_orders()

                # Verify mock exchange was called with mock credentials
                mock_get_conn.assert_called()
                call_kwargs = mock_get_conn.call_args[1]
                assert call_kwargs["exchange_config"]["api_key"] == "mock_api_key_12345"


class TestAggregateTPHybridMode:
    """Tests for hybrid mode in aggregate TP checking."""

    @pytest.mark.asyncio
    async def test_hybrid_mode_checks_aggregate_tp_with_open_orders(self, mock_monitor_service):
        """Test that hybrid mode positions check aggregate TP even with open orders."""
        session = AsyncMock()
        user = MagicMock()
        user.id = uuid.uuid4()
        user.encrypted_api_keys = {"mock": {}}

        open_order = MagicMock()
        open_order.status = OrderStatus.OPEN.value

        position = MagicMock()
        position.id = uuid.uuid4()
        position.exchange = "mock"
        position.tp_mode = "hybrid"  # Hybrid mode
        position.dca_orders = [open_order]  # Has open orders
        position.symbol = "BTCUSDT"
        position.side = "long"
        position.weighted_avg_entry = Decimal("50000")
        position.total_filled_quantity = Decimal("0.1")
        position.tp_aggregate_percent = Decimal("2")
        position.total_hedged_value_usd = Decimal("0")
        position.total_hedged_qty = Decimal("0")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [position]
        session.execute = AsyncMock(return_value=mock_result)

        mock_connector = AsyncMock()
        mock_connector.get_current_price = AsyncMock(return_value=Decimal("51500"))  # Above TP
        mock_connector.close = AsyncMock()

        order_service = AsyncMock()
        order_service.cancel_open_orders_for_group = AsyncMock()
        order_service.place_market_order = AsyncMock()
        mock_monitor_service.order_service_class.return_value = order_service

        position_repo = AsyncMock()
        position_repo.update = AsyncMock()
        mock_monitor_service.position_group_repository_class.return_value = position_repo

        mock_monitor_service.encryption_service = MagicMock()

        with patch("app.services.order_fill_monitor.get_exchange_connector", return_value=mock_connector):
            with patch("app.services.order_fill_monitor.broadcast_tp_hit", new_callable=AsyncMock):
                await mock_monitor_service._check_aggregate_tp_for_idle_positions(session, user)

        # Should have checked and executed TP
        order_service.place_market_order.assert_called_once()


class TestTriggerRiskEvaluationErrors:
    """Tests for error handling in _trigger_risk_evaluation_on_fill."""

    @pytest.mark.asyncio
    async def test_handles_risk_engine_exception(self, mock_monitor_service):
        """Test that exceptions in risk engine are handled gracefully."""
        from app.schemas.grid_config import RiskEngineConfig

        mock_monitor_service.risk_engine_config = RiskEngineConfig(evaluate_on_fill=True)

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_session = AsyncMock()

        with patch("app.services.order_fill_monitor.RiskEngineService") as mock_risk:
            mock_risk.side_effect = Exception("Risk engine error")

            # Should not raise
            await mock_monitor_service._trigger_risk_evaluation_on_fill(mock_user, mock_session)
