"""
Shared pytest fixtures for scenario-based trading tests.
"""

import pytest
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid
from app.models.user import User
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.pyramid import PyramidRepository
from app.schemas.grid_config import DCAGridConfig, DCALevelConfig, RiskEngineConfig
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService
from app.services.position.position_manager import PositionManagerService

from .fixtures import (
    ScenarioConfig,
    EntryType,
    QuantitySource,
    TPMode,
    create_dca_grid_config,
    create_dca_levels_config,
    create_mock_signal,
    create_position_group,
    create_dca_order,
    create_pyramid,
    calculate_expected_outcome
)


@pytest.fixture
def scenario_user_id():
    """Generate a random user ID for scenarios."""
    return uuid.uuid4()


@pytest.fixture
def scenario_mock_user(scenario_user_id):
    """Create a mock user for scenario tests."""
    def convert_decimals_to_str(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert_decimals_to_str(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_decimals_to_str(elem) for elem in obj]
        return obj

    risk_config_data = RiskEngineConfig().model_dump()

    user = MagicMock(spec=User)
    user.id = scenario_user_id
    user.username = "test_scenario_user"
    user.email = "scenario@test.com"
    user.webhook_secret = "test_secret"
    user.risk_config = convert_decimals_to_str(risk_config_data)
    user.encrypted_api_keys = {'mock': {'encrypted_data': 'test_encrypted_key'}}

    return user


@pytest.fixture
def scenario_mock_session():
    """Create a mock database session for scenarios."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()

    # Track added objects
    added_objects = []

    def track_add(obj):
        added_objects.append(obj)

    session.add.side_effect = track_add
    session._added_objects = added_objects

    # Mock refresh to set IDs on new objects
    async def mock_refresh(obj):
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = uuid.uuid4()

    session.refresh = AsyncMock(side_effect=mock_refresh)

    # Mock execute for queries
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    session.execute.return_value = mock_result

    return session


@pytest.fixture
def scenario_mock_session_factory(scenario_mock_session):
    """Create a session factory that yields the mock session."""
    @asynccontextmanager
    async def factory():
        yield scenario_mock_session

    return factory


@pytest.fixture
def scenario_mock_exchange_connector():
    """Create a mock exchange connector for scenarios."""
    connector = AsyncMock()

    # Default responses
    connector.get_current_price = AsyncMock(return_value=Decimal("100.0"))
    connector.get_symbol_info = AsyncMock(return_value={
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "tickSize": "0.01",
        "stepSize": "0.00001",
        "minQty": "0.00001",
        "minNotional": "10"
    })
    connector.get_trading_fee_rate = AsyncMock(return_value=0.001)  # 0.1% fee

    # Order placement
    connector.place_order = AsyncMock(return_value={
        "orderId": str(uuid.uuid4()),
        "status": "NEW",
        "executedQty": "0",
        "avgPrice": "0"
    })

    # Order cancellation
    connector.cancel_order = AsyncMock(return_value={"status": "CANCELED"})

    # Order status check
    connector.get_order_status = AsyncMock(return_value={
        "status": "NEW",
        "executedQty": "0",
        "avgPrice": "0"
    })

    return connector


@pytest.fixture
def scenario_mock_order_service():
    """Create a mock order service for scenarios."""
    service = MagicMock(spec=OrderService)
    service.submit_order = AsyncMock()
    service.cancel_order = AsyncMock()
    service.cancel_open_orders_for_group = AsyncMock()
    service.close_position_market = AsyncMock()
    service.place_tp_order = AsyncMock()
    service.place_aggregate_tp_order = AsyncMock()
    service.update_aggregate_tp_order = AsyncMock()

    return service


@pytest.fixture
def scenario_mock_order_service_class(scenario_mock_order_service):
    """Create a mock order service class that returns the mock instance."""
    mock_class = MagicMock(return_value=scenario_mock_order_service)
    return mock_class


@pytest.fixture
def scenario_mock_grid_calculator():
    """Create a mock grid calculator service."""
    calculator = MagicMock(spec=GridCalculatorService)

    def mock_calculate_levels(
        base_price,
        total_quote_amount,
        levels,
        symbol_info=None,
        side="long"
    ):
        """Generate realistic DCA levels based on config."""
        result = []
        for i, level in enumerate(levels):
            # Calculate price based on gap
            gap = Decimal(str(level.gap_percent)) / 100
            if side == "long":
                price = base_price * (Decimal("1") + gap)
            else:
                price = base_price * (Decimal("1") - gap)

            # Calculate quantity based on weight
            weight = Decimal(str(level.weight_percent)) / 100
            level_capital = total_quote_amount * weight
            quantity = level_capital / price

            # Calculate TP price
            tp_percent = Decimal(str(level.tp_percent)) / 100
            if side == "long":
                tp_price = price * (Decimal("1") + tp_percent)
            else:
                tp_price = price * (Decimal("1") - tp_percent)

            result.append({
                "leg_index": i,
                "price": price,
                "quantity": quantity,
                "gap_percent": level.gap_percent,
                "weight_percent": level.weight_percent,
                "tp_percent": level.tp_percent,
                "tp_price": tp_price
            })

        return result

    calculator.calculate_dca_levels.side_effect = mock_calculate_levels
    calculator.calculate_order_quantities.side_effect = GridCalculatorService.calculate_order_quantities

    return calculator


@pytest.fixture
def scenario_mock_position_group_repository():
    """Create a mock position group repository."""
    repo = MagicMock(spec=PositionGroupRepository)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_with_orders = AsyncMock(return_value=None)
    repo.increment_pyramid_count = AsyncMock(return_value=1)

    return repo


@pytest.fixture
def scenario_mock_position_group_repository_class(scenario_mock_position_group_repository):
    """Create a class that returns the mock repository."""
    mock_class = MagicMock(return_value=scenario_mock_position_group_repository)
    return mock_class


@pytest.fixture
def scenario_mock_dca_order_repository():
    """Create a mock DCA order repository."""
    repo = MagicMock(spec=DCAOrderRepository)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_open_orders_by_group_id = AsyncMock(return_value=[])
    repo.get_all_orders_by_group_id = AsyncMock(return_value=[])

    return repo


@pytest.fixture
def scenario_mock_pyramid_repository():
    """Create a mock pyramid repository."""
    repo = MagicMock(spec=PyramidRepository)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_by_group_id = AsyncMock(return_value=[])

    return repo


@pytest.fixture
def create_scenario_position_manager(
    scenario_mock_session_factory,
    scenario_mock_exchange_connector,
    scenario_mock_order_service_class,
    scenario_mock_position_group_repository_class,
    scenario_mock_grid_calculator,
    scenario_mock_user
):
    """Factory to create a PositionManagerService configured for a scenario."""

    def factory(scenario: ScenarioConfig):
        dca_config = create_dca_grid_config(scenario)

        service = PositionManagerService(
            session_factory=scenario_mock_session_factory,
            exchange_connector=scenario_mock_exchange_connector,
            dca_config=dca_config,
            user=scenario_mock_user,
            grid_calculator=scenario_mock_grid_calculator,
            order_service_class=scenario_mock_order_service_class,
            position_group_repository_class=scenario_mock_position_group_repository_class
        )

        return service

    return factory


# ==========================================
# Scenario-specific fixtures
# ==========================================

@pytest.fixture
def limit_entry_scenario():
    """Create a basic limit entry scenario."""
    return ScenarioConfig(
        scenario_id="test_limit",
        description="Test limit entry scenario",
        entry_type=EntryType.LIMIT,
        dca_levels=1,
        tp_mode=TPMode.PER_LEG
    )


@pytest.fixture
def market_entry_scenario():
    """Create a basic market entry scenario."""
    return ScenarioConfig(
        scenario_id="test_market",
        description="Test market entry scenario",
        entry_type=EntryType.MARKET,
        dca_levels=1,
        tp_mode=TPMode.PER_LEG
    )


@pytest.fixture
def multi_level_scenario():
    """Create a multi-level DCA scenario."""
    return ScenarioConfig(
        scenario_id="test_multi_level",
        description="Test multi-level DCA scenario",
        entry_type=EntryType.LIMIT,
        dca_levels=3,
        tp_mode=TPMode.AGGREGATE
    )


@pytest.fixture
def multi_pyramid_scenario():
    """Create a multi-pyramid scenario."""
    return ScenarioConfig(
        scenario_id="test_multi_pyramid",
        description="Test multi-pyramid scenario",
        entry_type=EntryType.LIMIT,
        max_pyramids=2,
        pyramid_count_to_test=2,
        dca_levels=2,
        tp_mode=TPMode.PYRAMID_AGGREGATE
    )


@pytest.fixture
def hybrid_tp_scenario():
    """Create a hybrid TP scenario."""
    return ScenarioConfig(
        scenario_id="test_hybrid",
        description="Test hybrid TP scenario",
        entry_type=EntryType.LIMIT,
        dca_levels=3,
        tp_mode=TPMode.HYBRID
    )


@pytest.fixture
def capital_override_scenario():
    """Create a capital override scenario."""
    return ScenarioConfig(
        scenario_id="test_override",
        description="Test capital override scenario",
        entry_type=EntryType.LIMIT,
        quantity_source=QuantitySource.OVERRIDE,
        custom_capital_usd=Decimal("300"),
        dca_levels=2,
        tp_mode=TPMode.PER_LEG
    )


@pytest.fixture
def short_position_scenario():
    """Create a short position scenario."""
    return ScenarioConfig(
        scenario_id="test_short",
        description="Test short position scenario",
        entry_type=EntryType.LIMIT,
        side="short",
        dca_levels=2,
        tp_mode=TPMode.PER_LEG
    )


# ==========================================
# Helper fixtures for test assertions
# ==========================================

@pytest.fixture
def assert_orders_created():
    """Fixture that returns an assertion helper for order creation."""

    def _assert(orders, scenario, expected_count):
        assert len(orders) == expected_count, f"Expected {expected_count} orders, got {len(orders)}"

        for order in orders:
            expected_side = "buy" if scenario.side == "long" else "sell"
            assert order.side == expected_side, f"Expected side {expected_side}, got {order.side}"
            assert order.symbol == scenario.symbol.replace("/", "")

    return _assert


@pytest.fixture
def assert_position_created():
    """Fixture that returns an assertion helper for position creation."""

    def _assert(position, scenario):
        assert position is not None, "Position should not be None"
        assert position.symbol == scenario.symbol.replace("/", "")
        assert position.side == scenario.side
        assert position.tp_mode == scenario.tp_mode.value
        assert position.max_pyramids == scenario.max_pyramids

    return _assert


@pytest.fixture
def simulate_order_fill(scenario_mock_dca_order_repository):
    """Fixture that simulates filling an order."""

    async def _simulate(order: DCAOrder, fill_price: Decimal = None, fill_qty: Decimal = None):
        order.status = OrderStatus.FILLED.value
        order.filled_quantity = fill_qty or order.quantity
        order.avg_fill_price = fill_price or order.price
        order.fee = (order.filled_quantity * order.avg_fill_price) * Decimal("0.001")  # 0.1% fee
        order.fee_currency = "USDT"
        return order

    return _simulate


@pytest.fixture
def simulate_tp_hit():
    """Fixture that simulates a take-profit being hit."""

    async def _simulate(order: DCAOrder, tp_fill_price: Decimal = None):
        order.tp_hit = True
        if not tp_fill_price:
            tp_fill_price = order.tp_price
        return order, tp_fill_price

    return _simulate
