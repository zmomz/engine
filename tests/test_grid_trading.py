import pytest
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.grid_calculator import GridCalculatorService, ValidationError
from app.services.take_profit_service import TakeProfitService, is_tp_reached, calculate_aggregate_tp_price, is_price_beyond_target, check_take_profit_conditions
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder, OrderStatus
from app.repositories.position_group import PositionGroupRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.db.database import AsyncSessionLocal

@pytest.fixture
def mock_position_group():
    return PositionGroup(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        status="active",
        base_entry_price=Decimal("60000"),
        weighted_avg_entry=Decimal("59500"),
        total_dca_legs=3,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("1.0")
    )

@pytest.fixture
def mock_dca_order_filled(mock_position_group):
    return DCAOrder(
        id=uuid.uuid4(),
        group_id=mock_position_group.id,
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="long",
        order_type="limit",
        price=Decimal("59000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("-1.0"),
        weight_percent=Decimal("30"),
        tp_percent=Decimal("1.0"),
        tp_price=Decimal("59590"), # 59000 * (1 + 1/100)
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("0.001"),
        avg_fill_price=Decimal("59000")
    )

@pytest.fixture
def mock_dca_order_open(mock_position_group):
    return DCAOrder(
        id=uuid.uuid4(),
        group_id=mock_position_group.id,
        pyramid_id=uuid.uuid4(),
        leg_index=1,
        symbol="BTC/USDT",
        side="long",
        order_type="limit",
        price=Decimal("58000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("-2.0"),
        weight_percent=Decimal("30"),
        tp_percent=Decimal("0.5"),
        tp_price=Decimal("58290"), # 58000 * (1 + 0.5/100)
        status=OrderStatus.OPEN,
        filled_quantity=Decimal("0"),
        avg_fill_price=None
    )

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.get_active_position_groups = AsyncMock()
    mock_class = MagicMock(spec=PositionGroupRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_dca_order_repository_class():
    mock_instance = MagicMock(spec=DCAOrderRepository)
    mock_instance.get_open_and_partially_filled_orders = AsyncMock()
    mock_class = MagicMock(spec=DCAOrderRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_order_service_class():
    mock_instance = AsyncMock(spec=OrderService)
    mock_class = MagicMock(spec=OrderService, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    return AsyncMock(spec=ExchangeInterface)

from contextlib import asynccontextmanager

# ... (other imports)

# ... (other fixtures)

@pytest.fixture
def mock_session_factory():
    @asynccontextmanager
    async def factory():
        mock_session_obj = AsyncMock(spec=AsyncSession)
        try:
            yield mock_session_obj
        finally:
            # In a real scenario, you might have cleanup code here.
            # For a mock, this might not be strictly necessary but is good practice.
            pass
    return factory

# ... (rest of the file)

@pytest.fixture
def take_profit_service(
    mock_position_group_repository_class,
    mock_dca_order_repository_class,
    mock_order_service_class,
    mock_exchange_connector,
    mock_session_factory
):
    return TakeProfitService(
        position_group_repository_class=mock_position_group_repository_class,
        dca_order_repository_class=mock_dca_order_repository_class,
        order_service_class=mock_order_service_class,
        exchange_connector=mock_exchange_connector,
        session_factory=mock_session_factory
    )

@pytest.fixture
def mock_precision_rules():
    return {
        "tick_size": Decimal("0.01"),
        "step_size": Decimal("0.000001"),
        "min_qty": Decimal("0.0001"),
        "min_notional": Decimal("10.0")
    }

@pytest.mark.asyncio
async def test_calculate_dca_levels_long_side(mock_precision_rules):
    """
    Test that the GridCalculatorService generates correct DCA levels for long side.
    """
    base_price = Decimal("100.00")
    dca_config = [
        {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
        {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5}
    ]
    side = "long"

    levels = GridCalculatorService.calculate_dca_levels(base_price, dca_config, side, mock_precision_rules)

    assert len(levels) == 3
    assert levels[0]["price"] == Decimal("100.00")
    assert levels[0]["tp_price"] == Decimal("101.00")
    assert levels[1]["price"] == Decimal("99.50")
    assert levels[1]["tp_price"] == Decimal("99.99") # 99.50 * (1 + 0.5/100) = 99.9975, rounded down to 0.01
    assert levels[2]["price"] == Decimal("99.00")
    assert levels[2]["tp_price"] == Decimal("99.49") # 99.00 * (1 + 0.5/100) = 99.495, rounded down to 0.01

@pytest.mark.asyncio
async def test_calculate_dca_levels_short_side(mock_precision_rules):
    """
    Test that the GridCalculatorService generates correct DCA levels for short side.
    """
    base_price = Decimal("100.00")
    dca_config = [
        {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
        {"gap_percent": 0.5, "weight_percent": 20, "tp_percent": 0.5},
        {"gap_percent": 1.0, "weight_percent": 20, "tp_percent": 0.5}
    ]
    side = "short"

    levels = GridCalculatorService.calculate_dca_levels(base_price, dca_config, side, mock_precision_rules)

    assert len(levels) == 3
    assert levels[0]["price"] == Decimal("100.00")
    assert levels[0]["tp_price"] == Decimal("99.00")
    assert levels[1]["price"] == Decimal("99.50")
    assert levels[1]["tp_price"] == Decimal("99.00") # 99.50 * (1 - 0.5/100) = 99.0025, rounded down to 0.01
    assert levels[2]["price"] == Decimal("99.00")
    assert levels[2]["tp_price"] == Decimal("98.50") # 99.00 * (1 - 0.5/100) = 98.505, rounded down to 0.01

@pytest.mark.asyncio
async def test_calculate_order_quantities_valid(mock_precision_rules):
    """
    Test that calculate_order_quantities correctly assigns quantities.
    """
    dca_levels = [
        {"leg_index": 0, "price": Decimal("100.00"), "gap_percent": Decimal("0.0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("1.0"), "tp_price": Decimal("101.00")},
        {"leg_index": 1, "price": Decimal("99.50"), "gap_percent": Decimal("-0.5"), "weight_percent": Decimal("30"), "tp_percent": Decimal("0.5"), "tp_price": Decimal("99.9975")}
    ]
    total_capital_usd = Decimal("1000.00")

    calculated_levels = GridCalculatorService.calculate_order_quantities(dca_levels, total_capital_usd, mock_precision_rules)

    assert len(calculated_levels) == 2
    assert calculated_levels[0]["quantity"] == Decimal("2.000000") # (1000 * 0.2) / 100 = 2
    assert calculated_levels[1]["quantity"] == Decimal("3.015075") # (1000 * 0.3) / 99.50 = 3.01507537..., rounded down to 0.000001

@pytest.mark.asyncio
async def test_calculate_order_quantities_min_qty_error(mock_precision_rules):
    """
    Test that calculate_order_quantities raises ValidationError for min_qty.
    """
    dca_levels = [
        {"leg_index": 0, "price": Decimal("100000.00"), "gap_percent": Decimal("0.0"), "weight_percent": Decimal("1"), "tp_percent": Decimal("1.0"), "tp_price": Decimal("101000.00")}
    ]
    total_capital_usd = Decimal("10.00") # This will result in a very small quantity

    with pytest.raises(ValidationError, match="Quantity .* below minimum .*"):
        GridCalculatorService.calculate_order_quantities(dca_levels, total_capital_usd, mock_precision_rules)


@pytest.mark.asyncio
async def test_take_profit_service_per_leg_mode(take_profit_service, mock_position_group, mock_dca_order_filled, mock_dca_order_open, mock_exchange_connector, mock_position_group_repository_class, mock_dca_order_repository_class):
    """
    Test the 'per_leg' take-profit mode.
    """
    mock_position_group.tp_mode = "per_leg"
    mock_position_group.dca_orders = [mock_dca_order_filled, mock_dca_order_open]

    # Mock repository to return the position group
    mock_position_group_repository_class.return_value.get_active_position_groups.return_value = [mock_position_group]

    # Mock exchange connector to return a price that triggers TP for mock_dca_order_filled
    mock_exchange_connector.get_current_price.return_value = Decimal("59600") # Above 59590

    # Run one iteration of the monitor loop
    await take_profit_service.check_positions()

    # Assertions
    mock_exchange_connector.get_current_price.assert_called_with(mock_position_group.symbol)
    mock_dca_order_repository_class.return_value.update.assert_called_with(mock_dca_order_filled.id, {"tp_hit": True})
    mock_dca_order_repository_class.return_value.update.assert_called_once()

@pytest.mark.asyncio
async def test_take_profit_service_aggregate_mode(take_profit_service, mock_position_group, mock_dca_order_filled, mock_dca_order_open, mock_exchange_connector, mock_position_group_repository_class, mock_dca_order_repository_class):
    """
    Test the 'aggregate' take-profit mode.
    """
    mock_position_group.tp_mode = "aggregate"
    mock_position_group.dca_orders = [mock_dca_order_filled, mock_dca_order_open]
    mock_position_group.weighted_avg_entry = Decimal("59000")
    mock_position_group.tp_aggregate_percent = Decimal("1.0") # TP at 59000 * (1 + 1/100) = 59590

    # Mock repository to return the position group
    mock_position_group_repository_class.return_value.get_active_position_groups.return_value = [mock_position_group]

    # Mock exchange connector to return a price that triggers aggregate TP
    mock_exchange_connector.get_current_price.return_value = Decimal("59600") # Above 59590

    # Run one iteration of the monitor loop
    await take_profit_service.check_positions()

    # Assertions
    mock_exchange_connector.get_current_price.assert_called_with(mock_position_group.symbol)
    # Both filled orders should be marked for TP hit
    assert mock_dca_order_repository_class.return_value.update.call_count == 1 # Only one update call for the filled order
    mock_dca_order_repository_class.return_value.update.assert_called_with(mock_dca_order_filled.id, {"tp_hit": True})

@pytest.mark.asyncio
async def test_take_profit_service_hybrid_mode_per_leg_first(take_profit_service, mock_position_group, mock_dca_order_filled, mock_dca_order_open, mock_exchange_connector, mock_position_group_repository_class, mock_dca_order_repository_class):
    """
    Test the 'hybrid' take-profit mode when per-leg triggers first.
    """
    mock_position_group.tp_mode = "hybrid"
    mock_position_group.dca_orders = [mock_dca_order_filled, mock_dca_order_open]
    mock_position_group.weighted_avg_entry = Decimal("50000") # Aggregate TP will be much higher
    mock_position_group.tp_aggregate_percent = Decimal("20.0") # TP at 50000 * (1 + 20/100) = 60000

    # Mock repository to return the position group
    mock_position_group_repository_class.return_value.get_active_position_groups.return_value = [mock_position_group]

    # Mock exchange connector to return a price that triggers per-leg TP for mock_dca_order_filled but not aggregate
    mock_exchange_connector.get_current_price.return_value = Decimal("59600") # Triggers mock_dca_order_filled TP (59590)

    # Run one iteration of the monitor loop
    await take_profit_service.check_positions()

    # Assertions
    mock_exchange_connector.get_current_price.assert_called_with(mock_position_group.symbol)
    mock_dca_order_repository_class.return_value.update.assert_called_with(mock_dca_order_filled.id, {"tp_hit": True})
    mock_dca_order_repository_class.return_value.update.assert_called_once()

@pytest.mark.asyncio
async def test_take_profit_service_hybrid_mode_aggregate_first(take_profit_service, mock_position_group, mock_dca_order_filled, mock_dca_order_open, mock_exchange_connector, mock_position_group_repository_class, mock_dca_order_repository_class):
    """
    Test the 'hybrid' take-profit mode when aggregate triggers first.
    """
    mock_position_group.tp_mode = "hybrid"
    mock_position_group.dca_orders = [mock_dca_order_filled, mock_dca_order_open]
    mock_position_group.weighted_avg_entry = Decimal("59000")
    mock_position_group.tp_aggregate_percent = Decimal("1.0") # TP at 59000 * (1 + 1/100) = 59590

    # Mock repository to return the position group
    mock_position_group_repository_class.return_value.get_active_position_groups.return_value = [mock_position_group]

    # Mock exchange connector to return a price that triggers aggregate TP (59590) but not per-leg for mock_dca_order_filled (59590)
    # Set filled order TP higher to ensure aggregate triggers first
    mock_dca_order_filled.tp_price = Decimal("60000")
    mock_exchange_connector.get_current_price.return_value = Decimal("59600") # Triggers aggregate TP

    # Run one iteration of the monitor loop
    await take_profit_service.check_positions()

    # Assertions
    mock_exchange_connector.get_current_price.assert_called_with(mock_position_group.symbol)
    # Both filled orders should be marked for TP hit
    assert mock_dca_order_repository_class.return_value.update.call_count == 1 # Only one update call for the filled order
    mock_dca_order_repository_class.return_value.update.assert_called_with(mock_dca_order_filled.id, {"tp_hit": True})

@pytest.mark.asyncio
async def test_is_tp_reached_long_side():
    order = DCAOrder(id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=0, symbol="BTC/USDT", side="long", order_type="limit", price=Decimal("100"), quantity=Decimal("1"), gap_percent=Decimal("0"), weight_percent=Decimal("0"), tp_percent=Decimal("0"), tp_price=Decimal("101"), status=OrderStatus.FILLED)
    assert is_tp_reached(order, Decimal("101.00"), "long") is True
    assert is_tp_reached(order, Decimal("100.99"), "long") is False

@pytest.mark.asyncio
async def test_is_tp_reached_short_side():
    order = DCAOrder(id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=0, symbol="BTC/USDT", side="short", order_type="limit", price=Decimal("100"), quantity=Decimal("1"), gap_percent=Decimal("0"), weight_percent=Decimal("0"), tp_percent=Decimal("0"), tp_price=Decimal("99"), status=OrderStatus.FILLED)
    assert is_tp_reached(order, Decimal("99.00"), "short") is True
    assert is_tp_reached(order, Decimal("99.01"), "short") is False

@pytest.mark.asyncio
async def test_calculate_aggregate_tp_price_long_side():
    weighted_avg_entry = Decimal("100")
    tp_percent = Decimal("1")
    side = "long"
    assert calculate_aggregate_tp_price(weighted_avg_entry, tp_percent, side) == Decimal("101.00")

@pytest.mark.asyncio
async def test_calculate_aggregate_tp_price_short_side():
    weighted_avg_entry = Decimal("100")
    tp_percent = Decimal("1")
    side = "short"
    assert calculate_aggregate_tp_price(weighted_avg_entry, tp_percent, side) == Decimal("99.00")

@pytest.mark.asyncio
async def test_is_price_beyond_target_long_side():
    assert is_price_beyond_target(Decimal("101"), Decimal("100"), "long") is True
    assert is_price_beyond_target(Decimal("99"), Decimal("100"), "long") is False

@pytest.mark.asyncio
async def test_is_price_beyond_target_short_side():
    assert is_price_beyond_target(Decimal("99"), Decimal("100"), "short") is True
    assert is_price_beyond_target(Decimal("101"), Decimal("100"), "short") is False

@pytest.mark.asyncio
async def test_position_manager_exit_logic():
    """
    Test that the PositionManagerService correctly handles exit signals.
    """
    # TODO: Implement test logic here
    assert True