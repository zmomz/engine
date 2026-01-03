"""
Additional tests for services/position/position_manager.py to achieve higher coverage.
Focuses on update_position_stats, _check_pyramid_aggregate_tp, and edge cases.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

from app.services.position.position_manager import PositionManagerService
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.exchange = "binance"
    user.encrypted_api_keys = {"binance": {"encrypted_data": "test_key"}}
    return user


@pytest.fixture
def mock_exchange_connector():
    """Create a mock exchange connector."""
    connector = AsyncMock()
    connector.get_current_price = AsyncMock(return_value=Decimal("50000"))
    connector.get_precision_rules = AsyncMock(return_value={
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    })
    connector.cancel_order = AsyncMock()
    connector.close = AsyncMock()
    return connector


@pytest.fixture
def position_group(mock_user):
    """Create a test position group."""
    pg = PositionGroup(
        id=uuid.uuid4(),
        user_id=mock_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.LIVE,
        total_dca_legs=3,
        filled_dca_legs=0,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode="aggregate",
        tp_aggregate_percent=Decimal("3"),
        pyramid_count=1,
        max_pyramids=3
    )
    pg.dca_orders = []
    pg.pyramids = []
    return pg


@pytest.fixture
def filled_orders(position_group):
    """Create filled DCA orders."""
    pyramid_id = uuid.uuid4()
    orders = [
        DCAOrder(
            id=uuid.uuid4(),
            group_id=position_group.id,
            pyramid_id=pyramid_id,
            leg_index=0,
            side="buy",
            price=Decimal("50000"),
            quantity=Decimal("0.01"),
            filled_quantity=Decimal("0.01"),
            avg_fill_price=Decimal("50000"),
            status=OrderStatus.FILLED,
            filled_at=datetime.utcnow() - timedelta(hours=1),
            tp_hit=False
        ),
        DCAOrder(
            id=uuid.uuid4(),
            group_id=position_group.id,
            pyramid_id=pyramid_id,
            leg_index=1,
            side="buy",
            price=Decimal("49500"),
            quantity=Decimal("0.01"),
            filled_quantity=Decimal("0.01"),
            avg_fill_price=Decimal("49500"),
            status=OrderStatus.FILLED,
            filled_at=datetime.utcnow(),
            tp_hit=False
        )
    ]
    return orders


@pytest.fixture
def pyramid(position_group):
    """Create a test pyramid."""
    return Pyramid(
        id=uuid.uuid4(),
        group_id=position_group.id,
        pyramid_index=0,
        status=PyramidStatus.SUBMITTED,
        entry_price=Decimal("50000"),
        dca_config={"pyramid_tp_percents": {"0": "3"}}
    )


@pytest.fixture
def mock_session(pyramid, mock_user):
    """Create a mock async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.expire_all = MagicMock()  # Sync method used in position_closer
    # Return pyramid or user based on type
    async def mock_get(model, id):
        if model == Pyramid:
            return pyramid
        if model == User:
            return mock_user
        return None
    session.get = AsyncMock(side_effect=mock_get)

    # Mock execute to return a result with sync fetchall()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []  # Default empty list
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Create a session factory."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def factory():
        yield mock_session
    return factory


@pytest.fixture
def position_manager_service(mock_session_factory, mock_user):
    """Create PositionManagerService instance."""
    mock_repo_class = MagicMock(spec=PositionGroupRepository)
    mock_grid_calc = MagicMock(spec=GridCalculatorService)
    mock_order_service_class = MagicMock(spec=OrderService)

    return PositionManagerService(
        session_factory=mock_session_factory,
        user=mock_user,
        position_group_repository_class=mock_repo_class,
        grid_calculator_service=mock_grid_calc,
        order_service_class=mock_order_service_class
    )


# --- Tests for update_position_stats ---

@pytest.mark.asyncio
async def test_update_position_stats_calculates_long_stats(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats correctly calculates stats for long position."""
    position_group.dca_orders = filled_orders
    position_group.side = "long"

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    assert result is not None
    assert result.total_filled_quantity > 0

    # CRITICAL: Verify state was persisted via repository update
    mock_repo.update.assert_called_once()
    updated_position = mock_repo.update.call_args[0][0]
    assert updated_position.total_filled_quantity > 0, \
        "Position total_filled_quantity must be updated after stats calculation"


@pytest.mark.asyncio
async def test_update_position_stats_with_exit_orders(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats correctly calculates stats with exit orders.

    For SPOT trading: All positions are "long" (buy to enter, sell to exit).
    This test verifies that sell orders (exits) are processed correctly.
    """
    # Add exit order
    exit_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=position_group.id,
        pyramid_id=None,
        leg_index=999,
        side="sell",  # Exit order
        price=Decimal("50500"),
        quantity=Decimal("0.005"),
        filled_quantity=Decimal("0.005"),
        avg_fill_price=Decimal("50500"),
        status=OrderStatus.FILLED,
        filled_at=datetime.utcnow(),
        tp_hit=False
    )
    position_group.dca_orders = filled_orders + [exit_order]
    position_group.side = "long"

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    assert result is not None

    # CRITICAL: Verify state was persisted via repository update
    mock_repo.update.assert_called_once()
    updated_position = mock_repo.update.call_args[0][0]
    assert updated_position.side == "long", \
        "Position side must remain long after stats calculation"
    # After partial exit, quantity should be reduced
    assert updated_position.total_filled_quantity < Decimal("0.02"), \
        "Total filled quantity should decrease after exit order"


@pytest.mark.asyncio
async def test_update_position_stats_updates_pyramid_status(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test update_position_stats updates pyramid status when all orders filled."""
    pyramid_id = pyramid.id
    for order in filled_orders:
        order.pyramid_id = pyramid_id

    position_group.dca_orders = filled_orders
    position_group.pyramids = [pyramid]

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    # Make session.get return user first, then pyramid
    async def mock_get_fn(model, id):
        if model == User:
            return mock_user
        if model == Pyramid:
            return pyramid
        return None
    mock_session.get = AsyncMock(side_effect=mock_get_fn)

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        with patch("app.services.position.position_manager.broadcast_entry_signal", new_callable=AsyncMock):
            result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Pyramid should be marked as FILLED - this is a state transition
    assert pyramid.status == PyramidStatus.FILLED, \
        "Pyramid status must transition to FILLED when all orders are filled"


@pytest.mark.asyncio
async def test_update_position_stats_transition_to_active(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test update_position_stats transitions to ACTIVE when all legs filled."""
    position_group.dca_orders = filled_orders
    position_group.status = PositionGroupStatus.LIVE
    position_group.total_dca_legs = 2
    position_group.pyramids = [pyramid]

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        with patch("app.services.position.position_manager.broadcast_status_change", new_callable=AsyncMock) as mock_broadcast:
            result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Verify state transition from LIVE to ACTIVE
    assert position_group.status == PositionGroupStatus.ACTIVE, \
        "Position must transition to ACTIVE when all DCA legs are filled"

    # CRITICAL: Verify state was persisted via repository update
    mock_repo.update.assert_called()
    updated_position = mock_repo.update.call_args[0][0]
    assert updated_position.status == PositionGroupStatus.ACTIVE, \
        "Updated position must have ACTIVE status persisted"

    # Verify broadcast was called with correct status
    mock_broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_stats_transition_to_partially_filled(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test update_position_stats transitions to PARTIALLY_FILLED."""
    # Only one order filled
    position_group.dca_orders = [filled_orders[0]]
    position_group.status = PositionGroupStatus.LIVE
    position_group.total_dca_legs = 5  # More legs expected
    position_group.pyramids = [pyramid]

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        with patch("app.services.position.position_manager.broadcast_status_change", new_callable=AsyncMock) as mock_broadcast:
            result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Verify state transition from LIVE to PARTIALLY_FILLED
    assert position_group.status == PositionGroupStatus.PARTIALLY_FILLED, \
        "Position must transition to PARTIALLY_FILLED when some legs filled but more expected"

    # CRITICAL: Verify state was persisted via repository update
    mock_repo.update.assert_called()
    updated_position = mock_repo.update.call_args[0][0]
    assert updated_position.status == PositionGroupStatus.PARTIALLY_FILLED, \
        "Updated position must have PARTIALLY_FILLED status persisted"


@pytest.mark.asyncio
async def test_update_position_stats_auto_close_all_tps_hit(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats auto-closes when all TPs hit (qty = 0)."""
    # Add exit order that closes the position
    exit_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=position_group.id,
        pyramid_id=None,
        leg_index=999,
        side="sell",  # Exit for long
        price=Decimal("51000"),
        quantity=Decimal("0.02"),
        filled_quantity=Decimal("0.02"),
        avg_fill_price=Decimal("51000"),
        status=OrderStatus.FILLED,
        filled_at=datetime.utcnow(),
        tp_hit=True
    )

    position_group.dca_orders = filled_orders + [exit_order]
    position_group.status = PositionGroupStatus.ACTIVE

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_order_service = MagicMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Verify state transition to CLOSED when all TPs hit
    assert position_group.status == PositionGroupStatus.CLOSED, \
        "Position must transition to CLOSED when all TPs hit and qty = 0"

    # CRITICAL: Verify state was persisted via repository update
    mock_repo.update.assert_called()
    updated_position = mock_repo.update.call_args[0][0]
    assert updated_position.status == PositionGroupStatus.CLOSED, \
        "Updated position must have CLOSED status persisted"

    # Verify cancel_open_orders was called to clean up remaining orders
    mock_order_service.cancel_open_orders_for_group.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_stats_triggers_aggregate_tp_long(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats triggers aggregate TP for long position."""
    position_group.dca_orders = filled_orders
    position_group.status = PositionGroupStatus.ACTIVE
    position_group.tp_mode = "aggregate"
    position_group.tp_aggregate_percent = Decimal("2")
    position_group.side = "long"

    # Set price above TP threshold
    mock_exchange_connector.get_current_price.return_value = Decimal("51500")

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_order_service = MagicMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    mock_order_service.place_market_order = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock) as mock_broadcast_tp:
            result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Should have executed TP via market order
    mock_order_service.place_market_order.assert_called_once()

    # CRITICAL: Verify market order was placed with correct side (sell for long exit)
    market_order_call = mock_order_service.place_market_order.call_args
    assert market_order_call is not None, "Market order must be placed for aggregate TP"

    # CRITICAL: Verify state transition to CLOSED after aggregate TP
    assert position_group.status == PositionGroupStatus.CLOSED, \
        "Position must transition to CLOSED after aggregate TP execution"

    # Verify TP hit was broadcast
    mock_broadcast_tp.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_stats_triggers_aggregate_tp_sell_side(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats triggers aggregate TP and sells with correct side.

    For SPOT trading: All positions are "long", so TP always uses SELL to exit.
    This test verifies the market order uses the correct side.
    """
    position_group.side = "long"
    for order in filled_orders:
        order.side = "buy"

    position_group.dca_orders = filled_orders
    position_group.status = PositionGroupStatus.ACTIVE
    position_group.tp_mode = "aggregate"
    position_group.tp_aggregate_percent = Decimal("2")

    # Set price above TP threshold for long
    mock_exchange_connector.get_current_price.return_value = Decimal("51500")

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_order_service = MagicMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    mock_order_service.place_market_order = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock) as mock_broadcast_tp:
            result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Should have executed TP via market order
    mock_order_service.place_market_order.assert_called_once()

    # CRITICAL: Verify market order was placed with correct side (SELL for long exit in spot trading)
    market_order_call = mock_order_service.place_market_order.call_args
    assert market_order_call is not None, "Market order must be placed for aggregate TP"
    assert market_order_call.kwargs.get("side") == "SELL", \
        "For spot trading, TP exit must use SELL side"

    # Verify TP hit was broadcast
    mock_broadcast_tp.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_stats_hybrid_tp(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats with hybrid TP mode."""
    position_group.dca_orders = filled_orders
    position_group.status = PositionGroupStatus.ACTIVE
    position_group.tp_mode = "hybrid"
    position_group.tp_aggregate_percent = Decimal("2")

    # Set price above TP threshold
    mock_exchange_connector.get_current_price.return_value = Decimal("51500")

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_order_service = MagicMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    mock_order_service.place_market_order = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock) as mock_broadcast_tp:
            result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # CRITICAL: Should have executed TP via market order for hybrid mode
    mock_order_service.place_market_order.assert_called_once()

    # CRITICAL: Verify hybrid TP mode triggers aggregate TP correctly
    market_order_call = mock_order_service.place_market_order.call_args
    assert market_order_call is not None, "Market order must be placed for hybrid TP"

    # Verify TP hit was broadcast
    mock_broadcast_tp.assert_called_once()


@pytest.mark.asyncio
async def test_update_position_stats_user_not_found(
    position_manager_service, position_group, filled_orders
):
    """Test update_position_stats when user is not found."""
    position_group.dca_orders = filled_orders

    # Create a fresh mock session that returns None for user
    mock_session_local = AsyncMock()
    mock_session_local.add = MagicMock()
    mock_session_local.commit = AsyncMock()
    mock_session_local.flush = AsyncMock()
    mock_session_local.refresh = AsyncMock()
    mock_session_local.get = AsyncMock(return_value=None)  # User not found
    mock_session_local.execute = AsyncMock()

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    position_manager_service.position_group_repository_class.return_value = mock_repo

    result = await position_manager_service._execute_update_position_stats(mock_session_local, position_group.id)

    assert result is None


@pytest.mark.asyncio
async def test_update_position_stats_zero_invested(
    position_manager_service, mock_session, position_group, filled_orders, mock_user, mock_exchange_connector
):
    """Test update_position_stats handles zero invested USD."""
    position_group.dca_orders = filled_orders
    position_group.total_invested_usd = Decimal("0")

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_session.get.return_value = mock_user

    with patch.object(position_manager_service, '_get_exchange_connector_for_user', return_value=mock_exchange_connector):
        result = await position_manager_service._execute_update_position_stats(mock_session, position_group.id)

    # Should handle gracefully
    assert result is not None


# --- Tests for _check_pyramid_aggregate_tp ---

@pytest.mark.asyncio
async def test_check_pyramid_aggregate_tp_long(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test _check_pyramid_aggregate_tp for long position."""
    pyramid_id = pyramid.id
    for order in filled_orders:
        order.pyramid_id = pyramid_id

    position_group.side = "long"
    position_group.tp_mode = "pyramid_aggregate"
    position_group.tp_aggregate_percent = Decimal("2")

    # Mock the execute result for pyramid query
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pyramid]
    mock_session.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service.place_market_order = AsyncMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    # Price above TP target
    current_price = Decimal("51500")

    with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock):
        await position_manager_service._check_pyramid_aggregate_tp(
            session=mock_session,
            position_group=position_group,
            filled_orders=filled_orders,
            current_price=current_price,
            user=mock_user,
            exchange_connector=mock_exchange_connector,
            position_group_repo=mock_repo
        )

    mock_order_service.place_market_order.assert_called_once()




@pytest.mark.asyncio
async def test_check_pyramid_aggregate_tp_skips_already_tpd(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test _check_pyramid_aggregate_tp skips already TP'd orders."""
    pyramid_id = pyramid.id
    for order in filled_orders:
        order.pyramid_id = pyramid_id
        order.tp_hit = True  # Already TP'd

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pyramid]
    mock_session.execute.return_value = mock_result

    mock_repo = MagicMock()

    mock_order_service = MagicMock()
    mock_order_service.place_market_order = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    current_price = Decimal("51500")

    await position_manager_service._check_pyramid_aggregate_tp(
        session=mock_session,
        position_group=position_group,
        filled_orders=filled_orders,
        current_price=current_price,
        user=mock_user,
        exchange_connector=mock_exchange_connector,
        position_group_repo=mock_repo
    )

    # Should not place any orders
    mock_order_service.place_market_order.assert_not_called()


@pytest.mark.asyncio
async def test_check_pyramid_aggregate_tp_uses_default_percent(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test _check_pyramid_aggregate_tp uses default percent when not in config."""
    pyramid_id = pyramid.id
    pyramid.dca_config = {}  # No pyramid_tp_percents

    for order in filled_orders:
        order.pyramid_id = pyramid_id

    position_group.tp_aggregate_percent = Decimal("3")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pyramid]
    mock_session.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service.place_market_order = AsyncMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    current_price = Decimal("51600")

    with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock):
        await position_manager_service._check_pyramid_aggregate_tp(
            session=mock_session,
            position_group=position_group,
            filled_orders=filled_orders,
            current_price=current_price,
            user=mock_user,
            exchange_connector=mock_exchange_connector,
            position_group_repo=mock_repo
        )

    mock_order_service.place_market_order.assert_called_once()


@pytest.mark.asyncio
async def test_check_pyramid_aggregate_tp_cancels_tp_orders(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test _check_pyramid_aggregate_tp cancels existing TP orders."""
    pyramid_id = pyramid.id
    for order in filled_orders:
        order.pyramid_id = pyramid_id
        order.tp_order_id = f"tp_order_{order.id}"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pyramid]
    mock_session.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service.place_market_order = AsyncMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    current_price = Decimal("51500")

    with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock):
        await position_manager_service._check_pyramid_aggregate_tp(
            session=mock_session,
            position_group=position_group,
            filled_orders=filled_orders,
            current_price=current_price,
            user=mock_user,
            exchange_connector=mock_exchange_connector,
            position_group_repo=mock_repo
        )

    # Should cancel TP orders
    assert mock_exchange_connector.cancel_order.call_count == 2


@pytest.mark.asyncio
async def test_check_pyramid_aggregate_tp_handles_cancel_error(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test _check_pyramid_aggregate_tp handles TP order cancel errors."""
    pyramid_id = pyramid.id
    for order in filled_orders:
        order.pyramid_id = pyramid_id
        order.tp_order_id = f"tp_order_{order.id}"

    mock_exchange_connector.cancel_order.side_effect = Exception("Order not found")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pyramid]
    mock_session.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service.place_market_order = AsyncMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    current_price = Decimal("51500")

    with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock):
        # Should not raise
        await position_manager_service._check_pyramid_aggregate_tp(
            session=mock_session,
            position_group=position_group,
            filled_orders=filled_orders,
            current_price=current_price,
            user=mock_user,
            exchange_connector=mock_exchange_connector,
            position_group_repo=mock_repo
        )

    # Should still place market order
    mock_order_service.place_market_order.assert_called_once()


@pytest.mark.asyncio
async def test_check_pyramid_aggregate_tp_closes_all_pyramids(
    position_manager_service, mock_session, position_group, filled_orders, pyramid, mock_user, mock_exchange_connector
):
    """Test _check_pyramid_aggregate_tp closes position when all pyramids are closed."""
    pyramid.status = PyramidStatus.SUBMITTED
    pyramid_id = pyramid.id
    for order in filled_orders:
        order.pyramid_id = pyramid_id

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pyramid]  # Only one pyramid
    mock_session.execute.return_value = mock_result

    mock_repo = MagicMock()
    mock_repo.update = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service.place_market_order = AsyncMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    current_price = Decimal("51500")

    with patch("app.services.position.position_manager.broadcast_tp_hit", new_callable=AsyncMock):
        await position_manager_service._check_pyramid_aggregate_tp(
            session=mock_session,
            position_group=position_group,
            filled_orders=filled_orders,
            current_price=current_price,
            user=mock_user,
            exchange_connector=mock_exchange_connector,
            position_group_repo=mock_repo
        )

    # Position should be closed
    assert position_group.status == PositionGroupStatus.CLOSED
    mock_repo.update.assert_called_once()


# --- Tests for handle_exit_signal with session ---

@pytest.mark.asyncio
async def test_handle_exit_signal_with_session(
    position_manager_service, mock_session, position_group, mock_user, mock_exchange_connector
):
    """Test handle_exit_signal when session is provided."""
    position_group.dca_orders = [
        DCAOrder(status=OrderStatus.FILLED, filled_quantity=Decimal("0.01"), side="buy")
    ]

    mock_repo = MagicMock()
    mock_repo.get_with_orders = AsyncMock(return_value=position_group)
    mock_repo.update = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    mock_order_service = MagicMock()
    mock_order_service.cancel_open_orders_for_group = AsyncMock()
    mock_order_service.sync_orders_for_group = AsyncMock()
    mock_order_service.close_position_market = AsyncMock()
    position_manager_service.order_service_class.return_value = mock_order_service

    # Mock DB query to return filled orders
    mock_row = MagicMock()
    mock_row.side = "buy"
    mock_row.filled_quantity = Decimal("0.01")
    mock_row.status = "filled"
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Ensure get_trading_fee_rate is mocked
    mock_exchange_connector.get_trading_fee_rate = AsyncMock(return_value=0.001)

    with patch("app.services.position.position_closer.get_exchange_connector", return_value=mock_exchange_connector):
        with patch("app.services.position.position_closer.save_close_action", new_callable=AsyncMock):
            await position_manager_service.handle_exit_signal(
                position_group_id=position_group.id,
                session=mock_session
            )

    # CRITICAL: Verify cancel_open_orders was called to clean up pending orders
    mock_order_service.cancel_open_orders_for_group.assert_called_once()

    # CRITICAL: Verify close_position_market was called to exit the position
    mock_order_service.close_position_market.assert_called_once()

    # CRITICAL: Verify the position state was retrieved for exit handling
    mock_repo.get_with_orders.assert_called()
    # The method uses 'group_id' as the first positional argument
    assert mock_repo.get_with_orders.call_args[0][0] == position_group.id, \
        "Must retrieve position with orders for exit signal handling"


# --- Tests for update_risk_timer with provided position_group ---

@pytest.mark.asyncio
async def test_update_risk_timer_with_position_group(
    position_manager_service, mock_session, position_group
):
    """Test update_risk_timer when position_group is provided."""
    config = RiskEngineConfig()

    mock_repo = MagicMock()
    mock_repo.get = AsyncMock()
    position_manager_service.position_group_repository_class.return_value = mock_repo

    await position_manager_service._execute_update_risk_timer(
        session=mock_session,
        position_group_id=position_group.id,
        risk_config=config,
        position_group=position_group
    )

    # Should not call get since position_group was provided
    mock_repo.get.assert_not_called()


# --- Tests for _get_exchange_connector_for_user with legacy format ---

def test_get_exchange_connector_legacy_encrypted_data_only():
    """Test _get_exchange_connector_for_user with legacy encrypted_data only format."""
    user = MagicMock()
    user.encrypted_api_keys = {"encrypted_data": "legacy_key"}  # Legacy format

    service = PositionManagerService(
        session_factory=MagicMock(),
        user=user,
        position_group_repository_class=MagicMock(),
        grid_calculator_service=MagicMock(),
        order_service_class=MagicMock()
    )

    with patch("app.services.position.position_manager.get_exchange_connector") as mock_get:
        mock_get.return_value = MagicMock()
        result = service._get_exchange_connector_for_user(user, "binance")
        mock_get.assert_called_once_with("binance", {"encrypted_data": "legacy_key"})
