"""
Tests for the RiskEngineService.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import asyncio

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status

from app.services.risk_engine import RiskEngineService, select_loser_and_winners, calculate_partial_close_quantities
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.risk_action import RiskAction, RiskActionType
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.order_management import OrderService
from app.schemas.grid_config import RiskEngineConfig
from app.models.user import User # Import User model

# --- Fixtures for RiskEngineService ---

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.get_all = AsyncMock(return_value=[])
    mock_instance.update = AsyncMock()
    mock_instance.get_by_id = AsyncMock() # Added mock for get_by_id
    mock_class = MagicMock(spec=PositionGroupRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_risk_action_repository_class():
    mock_instance = MagicMock(spec=RiskActionRepository)
    mock_instance.create = AsyncMock()
    mock_class = MagicMock(spec=RiskActionRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    mock = AsyncMock(spec=ExchangeInterface)
    mock.get_current_price = AsyncMock(return_value=Decimal("50000")) # Default price
    return mock

@pytest.fixture
def mock_order_service():
    mock = AsyncMock(spec=OrderService)
    mock.cancel_order = AsyncMock()
    mock.place_market_order = AsyncMock()
    return mock

@pytest.fixture
def mock_session_factory():
    async def factory():
        mock_session_obj = AsyncMock()
        yield mock_session_obj
        await mock_session_obj.close()
    return factory

@pytest.fixture
def mock_dca_order_repository_class():
    mock_instance = MagicMock(spec=DCAOrderRepository)
    mock_instance.create = AsyncMock()
    mock_class = MagicMock(spec=DCAOrderRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_risk_engine_config():
    return RiskEngineConfig(
        loss_threshold_percent=Decimal("-10"),
        timer_start_condition="after_all_dca_filled",
        post_full_wait_minutes=60,
        max_winners_to_combine=3
    )

@pytest.fixture
def risk_engine_service(
    mock_session_factory,
    mock_position_group_repository_class,
    mock_risk_action_repository_class,
    mock_dca_order_repository_class,
    mock_exchange_connector,
    mock_order_service,
    mock_risk_engine_config
):
    return RiskEngineService(
        session_factory=mock_session_factory,
        position_group_repository_class=mock_position_group_repository_class,
        risk_action_repository_class=mock_risk_action_repository_class,
        dca_order_repository_class=mock_dca_order_repository_class,
        exchange_connector=mock_exchange_connector,
        order_service_class=lambda exchange_connector, dca_order_repo: mock_order_service,
        risk_engine_config=mock_risk_engine_config,
        polling_interval_seconds=0.01 # Fast polling for tests
    )

# --- Mock Models for selection logic tests ---

class MockPositionGroupForRisk(PositionGroup):
    def __init__(self, id, symbol, timeframe, side, status, unrealized_pnl_percent, unrealized_pnl_usd, created_at,
                 pyramid_count=0, max_pyramids=5, risk_timer_expires=None, risk_blocked=False, risk_skip_once=False,
                 weighted_avg_entry=Decimal("0"), total_filled_quantity=Decimal("0"), dca_orders=None, user_id=None):
        super().__init__(
            id=id,
            user_id=user_id if user_id else uuid.uuid4(),
            exchange="binance",
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            status=status,
            total_dca_legs=1, # Dummy value
            base_entry_price=Decimal("1"), # Dummy value
            weighted_avg_entry=weighted_avg_entry,
            total_invested_usd=Decimal("1"), # Dummy value
            total_filled_quantity=total_filled_quantity,
            unrealized_pnl_usd=unrealized_pnl_usd,
            unrealized_pnl_percent=unrealized_pnl_percent,
            realized_pnl_usd=Decimal("0"), # Dummy value
            tp_mode="per_leg", # Dummy value
            created_at=created_at,
            pyramid_count=pyramid_count,
            max_pyramids=max_pyramids,
            risk_timer_expires=risk_timer_expires,
            risk_blocked=risk_blocked,
            risk_skip_once=risk_skip_once
        )
        self.dca_orders = dca_orders if dca_orders is not None else []

class MockDCAOrderForRisk(DCAOrder):
    def __init__(self, id, group_id, pyramid_id, status, filled_quantity, avg_fill_price, side, symbol):
        super().__init__(
            id=id,
            group_id=group_id,
            pyramid_id=pyramid_id,
            exchange_order_id="test_order_id",
            leg_index=0,
            symbol=symbol,
            side=side,
            price=Decimal("1"), # Dummy
            quantity=Decimal("1"), # Dummy
            gap_percent=Decimal("0"), # Dummy
            weight_percent=Decimal("100"), # Dummy
            tp_percent=Decimal("1"), # Dummy
            tp_price=Decimal("1"), # Dummy
            status=status,
            filled_quantity=filled_quantity,
            avg_fill_price=avg_fill_price
        )

# --- Tests for select_loser_and_winners (standalone function) ---

def test_select_loser_highest_loss_percent():
    """Test loser selection based on highest loss percentage."""
    now = datetime.utcnow()
    pg1 = MockPositionGroupForRisk(uuid.uuid4(), "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg2 = MockPositionGroupForRisk(uuid.uuid4(), "ETHUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-5.0"), Decimal("-500"), now - timedelta(hours=2), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg3 = MockPositionGroupForRisk(uuid.uuid4(), "LTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-12.0"), Decimal("-800"), now - timedelta(hours=3), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())

    config = RiskEngineConfig(loss_threshold_percent=Decimal("-1.0"), require_full_pyramids=True, timer_start_condition="after_all_dca_filled", post_full_wait_minutes=60, max_winners_to_combine=3)
    
    loser, _, _ = select_loser_and_winners([pg1, pg2, pg3], config)
    assert loser.id == pg3.id # -12% is the highest loss

def test_select_loser_highest_loss_usd_on_tie():
    """Test loser selection based on highest unrealized loss USD when loss percentage is tied."""
    now = datetime.utcnow()
    pg1 = MockPositionGroupForRisk(uuid.uuid4(), "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg2 = MockPositionGroupForRisk(uuid.uuid4(), "ETHUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1200"), now - timedelta(hours=2), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg3 = MockPositionGroupForRisk(uuid.uuid4(), "LTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-800"), now - timedelta(hours=3), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())

    config = RiskEngineConfig(loss_threshold_percent=Decimal("-1.0"), require_full_pyramids=True, timer_start_condition="after_all_dca_filled", post_full_wait_minutes=60, max_winners_to_combine=3)
    
    loser, _, _ = select_loser_and_winners([pg1, pg2, pg3], config)
    assert loser.id == pg2.id # -1200 USD is the highest loss USD

def test_select_loser_oldest_trade_on_tie():
    """Test loser selection based on oldest trade when loss percentage and USD are tied."""
    now = datetime.utcnow()
    pg1 = MockPositionGroupForRisk(uuid.uuid4(), "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=3), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg2 = MockPositionGroupForRisk(uuid.uuid4(), "ETHUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=2), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg3 = MockPositionGroupForRisk(uuid.uuid4(), "LTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())

    config = RiskEngineConfig(loss_threshold_percent=Decimal("-1.0"), require_full_pyramids=True, timer_start_condition="after_all_dca_filled", post_full_wait_minutes=60, max_winners_to_combine=3)
    
    loser, _, _ = select_loser_and_winners([pg1, pg2, pg3], config)
    assert loser.id == pg1.id # Oldest trade

def test_select_winners_by_profit_descending():
    """Test winner selection based on unrealized profit USD (descending)."""
    now = datetime.utcnow()
    pg_loser = MockPositionGroupForRisk(uuid.uuid4(), "LOSER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1), user_id=uuid.uuid4())
    pg_winner1 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER1", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("500"), now - timedelta(hours=1), user_id=uuid.uuid4())
    pg_winner2 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER2", 15, "long", PositionGroupStatus.ACTIVE, Decimal("10.0"), Decimal("1200"), now - timedelta(hours=2))
    pg_winner3 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER3", 15, "long", PositionGroupStatus.ACTIVE, Decimal("2.0"), Decimal("200"), now - timedelta(hours=3))

    config = RiskEngineConfig(loss_threshold_percent=Decimal("-1.0"), require_full_pyramids=True, timer_start_condition="after_all_dca_filled", post_full_wait_minutes=60, max_winners_to_combine=3)
    
    _, winners, _ = select_loser_and_winners([pg_loser, pg_winner1, pg_winner2, pg_winner3], config)
    
    assert len(winners) == 3
    assert winners[0].id == pg_winner2.id # 1200 USD
    assert winners[1].id == pg_winner1.id # 500 USD
    assert winners[2].id == pg_winner3.id # 200 USD

def test_select_winners_max_winners_to_combine():
    """Test winner selection respects max_winners_to_combine."""
    now = datetime.utcnow()
    pg_loser = MockPositionGroupForRisk(uuid.uuid4(), "LOSER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1))
    pg_winner1 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER1", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("500"), now - timedelta(hours=1), user_id=uuid.uuid4())
    pg_winner2 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER2", 15, "long", PositionGroupStatus.ACTIVE, Decimal("10.0"), Decimal("1200"), now - timedelta(hours=2))
    pg_winner3 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER3", 15, "long", PositionGroupStatus.ACTIVE, Decimal("2.0"), Decimal("200"), now - timedelta(hours=3))
    pg_winner4 = MockPositionGroupForRisk(uuid.uuid4(), "WINNER4", 15, "long", PositionGroupStatus.ACTIVE, Decimal("7.0"), Decimal("700"), now - timedelta(hours=4))

    config = RiskEngineConfig(loss_threshold_percent=Decimal("-1.0"), require_full_pyramids=True, timer_start_condition="after_all_dca_filled", post_full_wait_minutes=60, max_winners_to_combine=2)
    
    _, winners, _ = select_loser_and_winners([pg_loser, pg_winner1, pg_winner2, pg_winner3, pg_winner4], config)
    
    assert len(winners) == 2
    assert winners[0].id == pg_winner2.id # 1200 USD
    assert winners[1].id == pg_winner4.id # 700 USD

def test_select_loser_no_eligible_losers():
    """Test no loser is selected if none meet criteria."""
    now = datetime.utcnow()
    pg1 = MockPositionGroupForRisk(uuid.uuid4(), "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-0.5"), Decimal("-50"), now - timedelta(hours=1), pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1)) # Below loss threshold
    pg2 = MockPositionGroupForRisk(uuid.uuid4(), "ETHUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-5.0"), Decimal("-500"), now - timedelta(hours=2), pyramid_count=2, risk_timer_expires=now - timedelta(minutes=1)) # Not full pyramids
    pg3 = MockPositionGroupForRisk(uuid.uuid4(), "LTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-800"), now - timedelta(hours=3), pyramid_count=5, risk_timer_expires=now + timedelta(minutes=1)) # Timer not expired

    config = RiskEngineConfig(loss_threshold_percent=Decimal("-1.0"), require_full_pyramids=True, timer_start_condition="after_all_dca_filled", post_full_wait_minutes=60, max_winners_to_combine=3)
    
    loser, winners, required_usd = select_loser_and_winners([pg1, pg2, pg3], config)
    assert loser is None
    assert len(winners) == 0
    assert required_usd == Decimal("0")

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_long_side(mock_exchange_connector):
    """Test partial close quantity calculation for long positions."""
    pg_winner = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("10.0"), Decimal("1000"), datetime.utcnow(),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10") # 10 units @ 100 = 1000 invested
    )
    # Simulate current price at 110, so unrealized profit is 100 (10 * (110-100))
    # We need 50 USD profit, so we need to close 5 units (5 * (110-100))
    
    required_usd = Decimal("50")
    precision_rules = {"WINNER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}}

    mock_exchange_connector.get_current_price.return_value = Decimal("110")
    close_plan = await calculate_partial_close_quantities(mock_exchange_connector, [pg_winner], required_usd, precision_rules)
    
    assert len(close_plan) == 1
    assert close_plan[0][0].id == pg_winner.id
    assert close_plan[0][1] == Decimal("5.000") # 50 USD profit / 10 USD profit per unit = 5 units

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_short_side(mock_exchange_connector):
    """Test partial close quantity calculation for short positions."""
    pg_winner = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER", 15, "short", PositionGroupStatus.ACTIVE, Decimal("10.0"), Decimal("1000"), datetime.utcnow(),
        weighted_avg_entry=Decimal("110"), total_filled_quantity=Decimal("10") # 10 units @ 110 = 1100 invested
    )
    # Simulate current price at 100, so unrealized profit is 100 (10 * (110-100))
    # We need 50 USD profit, so we need to close 5 units (5 * (110-100))
    
    required_usd = Decimal("50")
    precision_rules = {"WINNER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}}

    mock_exchange_connector.get_current_price.return_value = Decimal("100")
    close_plan = await calculate_partial_close_quantities(mock_exchange_connector, [pg_winner], required_usd, precision_rules)
    
    assert len(close_plan) == 1
    assert close_plan[0][0].id == pg_winner.id
    assert close_plan[0][1] == Decimal("5.000") # 50 USD profit / 10 USD profit per unit = 5 units

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_multiple_winners(mock_exchange_connector):
    """Test partial close quantity calculation with multiple winners."""
    pg_winner1 = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER1", 15, "long", PositionGroupStatus.ACTIVE, Decimal("10.0"), Decimal("100"), datetime.utcnow(),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10") # Current price 110
    )
    pg_winner2 = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER2", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("50"), datetime.utcnow(),
        weighted_avg_entry=Decimal("200"), total_filled_quantity=Decimal("10") # Current price 205
    )
    
    required_usd = Decimal("120") # Need 120 USD profit
    precision_rules = {
        "WINNER1": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "WINNER2": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }

    async def side_effect(symbol):
        if symbol == "WINNER1":
            return Decimal("110")
        elif symbol == "WINNER2":
            return Decimal("205")
        return Decimal("0")
    mock_exchange_connector.get_current_price.side_effect = side_effect
    
    close_plan = await calculate_partial_close_quantities(mock_exchange_connector, [pg_winner1, pg_winner2], required_usd, precision_rules)
    
    assert len(close_plan) == 2
    # Winner1: 100 USD profit available. Need 120. Take all 100. Close 10 units.
    assert close_plan[0][0].id == pg_winner1.id
    assert close_plan[0][1] == Decimal("10.000")
    
    # Winner2: 50 USD profit available. Need 20 more. Take 20. Close 4 units.
    assert close_plan[1][0].id == pg_winner2.id
    assert close_plan[1][1] == Decimal("4.000")

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_insufficient_profit(mock_exchange_connector):
    """Test partial close when total available profit is less than required."""
    pg_winner = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("50"), datetime.utcnow(),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10") # Current price 105
    )
    
    required_usd = Decimal("100") # Need 100 USD profit, but only 50 available
    precision_rules = {"WINNER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}}

    mock_exchange_connector.get_current_price.return_value = Decimal("105")
    close_plan = await calculate_partial_close_quantities(mock_exchange_connector, [pg_winner], required_usd, precision_rules)
    
    assert len(close_plan) == 1
    assert close_plan[0][0].id == pg_winner.id
    assert close_plan[0][1] == Decimal("10.000") # Closes all available, even if not enough

@pytest.mark.asyncio
async def test_calculate_partial_close_quantities_below_min_notional(mock_exchange_connector):
    """Test partial close skips winner if quantity results in below min_notional."""
    pg_winner = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("1.0"), Decimal("10"), datetime.utcnow(),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10") # Current price 101
    )
    
    required_usd = Decimal("5") # Need 5 USD profit
    precision_rules = {"WINNER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("1000")}} # High min_notional

    mock_exchange_connector.get_current_price.return_value = Decimal("101")
    close_plan = await calculate_partial_close_quantities(mock_exchange_connector, [pg_winner], required_usd, precision_rules)
    
    assert len(close_plan) == 0 # Should skip due to min_notional

# --- Tests for RiskEngineService methods ---

@pytest.mark.asyncio
async def test_risk_engine_service_start_and_stop_task(risk_engine_service):
    """Test starting and stopping the background risk engine task."""
    await risk_engine_service.start_monitoring_task()
    assert risk_engine_service._running is True
    assert risk_engine_service._monitor_task is not None
    assert not risk_engine_service._monitor_task.done() # Task should be running

    await risk_engine_service.stop_monitoring_task()
    assert risk_engine_service._running is False
    # Give a moment for the task to actually finish after cancellation
    await asyncio.sleep(0.05)
    assert risk_engine_service._monitor_task.done() # Task should be done after stopping

@pytest.mark.asyncio
async def test_risk_engine_service_monitoring_loop_error_handling(risk_engine_service, mock_position_group_repository_class):
    """Test that the monitoring loop handles exceptions gracefully and continues running."""
    mock_position_group_repository_class.return_value.get_all.side_effect = Exception("DB Error")

    await risk_engine_service.start_monitoring_task()
    assert risk_engine_service._running is True

    # Allow some time for the loop to run and encounter the error
    await asyncio.sleep(risk_engine_service.polling_interval_seconds * 2)

    # The loop should still be running despite the error
    assert risk_engine_service._running is True
    assert not risk_engine_service._monitor_task.done()

    await risk_engine_service.stop_monitoring_task()

@pytest.mark.asyncio
async def test_evaluate_positions_no_eligible_positions(risk_engine_service, mock_position_group_repository_class, mock_order_service):
    """Test evaluate_positions when no eligible positions are found."""
    mock_position_group_repository_class.return_value.get_all.return_value = []
    await risk_engine_service._evaluate_positions()
    mock_order_service.place_market_order.assert_not_called()
    risk_engine_service.risk_action_repository_class.return_value.create.assert_not_called()

@pytest.mark.asyncio
async def test_evaluate_positions_successful_offset(risk_engine_service, mock_position_group_repository_class, mock_order_service, mock_risk_action_repository_class):
    """Test successful offset of a losing position with winning positions."""
    now = datetime.utcnow()
    loser_pg = MockPositionGroupForRisk(
        uuid.uuid4(), "LOSER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1),
        pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    winner_pg1 = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER1", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("500"), now - timedelta(hours=2),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    winner_pg2 = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER2", 15, "long", PositionGroupStatus.ACTIVE, Decimal("7.0"), Decimal("700"), now - timedelta(hours=3),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    
    mock_position_group_repository_class.return_value.get_all.return_value = [loser_pg, winner_pg1, winner_pg2]
    
    # Mock current prices for calculation
    risk_engine_service.exchange_connector.get_current_price.side_effect = lambda symbol: {
        "LOSER": Decimal("90"),
        "WINNER1": Decimal("150"), # 500 profit from 10 units @ 100 avg entry
        "WINNER2": Decimal("170")  # 700 profit from 10 units @ 100 avg entry
    }.get(symbol, Decimal("0"))

    # Mock precision rules
    risk_engine_service.exchange_connector.get_precision_rules.return_value = {
        "LOSER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "WINNER1": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "WINNER2": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }

    # Set config for the test
    risk_engine_service.config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-1.0"), 
        require_full_pyramids=True, 
        timer_start_condition="after_all_dca_filled", 
        post_full_wait_minutes=60,
        max_winners_to_combine=3
    )

    await risk_engine_service._evaluate_positions()

    # Assertions
    assert mock_order_service.place_market_order.call_count == 3
    mock_order_service.place_market_order.assert_any_call(
        user_id=loser_pg.user_id,
        exchange=loser_pg.exchange,
        symbol=loser_pg.symbol,
        side="sell" if loser_pg.side == "long" else "buy",
        quantity=loser_pg.total_filled_quantity,
        position_group_id=loser_pg.id
    )
    # Loser needs 1000 USD. Winner1 provides 500 (closes 10 units). Winner2 provides 500 (closes 500/70 = 7.142 units)
    mock_order_service.place_market_order.assert_any_call(
        user_id=winner_pg1.user_id,
        exchange=winner_pg1.exchange,
        symbol=winner_pg1.symbol,
        side="sell" if winner_pg1.side == "long" else "buy",
        quantity=Decimal("6.000"), # Updated quantity
        position_group_id=winner_pg1.id
    )
    mock_order_service.place_market_order.assert_any_call(
        user_id=winner_pg2.user_id,
        exchange=winner_pg2.exchange,
        symbol=winner_pg2.symbol,
        side="sell" if winner_pg2.side == "long" else "buy",
        quantity=Decimal("10.000"), # Updated quantity
        position_group_id=winner_pg2.id
    )
    
    mock_risk_action_repository_class.return_value.create.assert_called_once()
    # Verify the risk action details
    call_args = mock_risk_action_repository_class.return_value.create.call_args[0][0]
    assert call_args.action_type == RiskActionType.OFFSET_LOSS
    assert call_args.group_id == loser_pg.id
    assert call_args.loser_group_id == loser_pg.id
    assert call_args.loser_pnl_usd == Decimal("-1000")
    assert len(call_args.winner_details) == 2
    assert any(d['group_id'] == str(winner_pg1.id) for d in call_args.winner_details)
    assert any(d['group_id'] == str(winner_pg2.id) for d in call_args.winner_details)

@pytest.mark.asyncio
async def test_evaluate_positions_insufficient_winner_profit(risk_engine_service, mock_position_group_repository_class, mock_order_service, mock_risk_action_repository_class):
    """Test offset when total winner profit is insufficient to cover loser."""
    now = datetime.utcnow()
    loser_pg = MockPositionGroupForRisk(
        uuid.uuid4(), "LOSER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-20.0"), Decimal("-2000"), now - timedelta(hours=1),
        pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    winner_pg1 = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER1", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("500"), now - timedelta(hours=2),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    
    mock_position_group_repository_class.return_value.get_all.return_value = [loser_pg, winner_pg1]
    
    risk_engine_service.exchange_connector.get_current_price.side_effect = lambda symbol: {
        "LOSER": Decimal("80"),
        "WINNER1": Decimal("150")
    }.get(symbol, Decimal("0"))

    risk_engine_service.exchange_connector.get_precision_rules.return_value = {
        "LOSER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "WINNER1": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }

    risk_engine_service.config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-1.0"), 
        require_full_pyramids=True, 
        timer_start_condition="after_all_dca_filled", 
        post_full_wait_minutes=60,
        max_winners_to_combine=3
    )

    await risk_engine_service._evaluate_positions()

    # Loser should still be closed
    assert mock_order_service.place_market_order.call_count == 2
    mock_order_service.place_market_order.assert_any_call(
        user_id=loser_pg.user_id,
        exchange=loser_pg.exchange,
        symbol=loser_pg.symbol,
        side="sell" if loser_pg.side == "long" else "buy",
        quantity=loser_pg.total_filled_quantity,
        position_group_id=loser_pg.id
    )
    # Winner1 should be fully closed (500 USD profit)
    mock_order_service.place_market_order.assert_any_call(
        user_id=winner_pg1.user_id,
        exchange=winner_pg1.exchange,
        symbol=winner_pg1.symbol,
        side="sell" if winner_pg1.side == "long" else "buy",
        quantity=Decimal("10.000"),
        position_group_id=winner_pg1.id
    )
    
    mock_risk_action_repository_class.return_value.create.assert_called_once()
    call_args = mock_risk_action_repository_class.return_value.create.call_args[0][0]
    assert call_args.loser_pnl_usd == Decimal("-2000")
    assert len(call_args.winner_details) == 1
    assert any(d['group_id'] == str(winner_pg1.id) for d in call_args.winner_details)

@pytest.mark.asyncio
async def test_evaluate_positions_order_placement_failure_rollback(risk_engine_service, mock_position_group_repository_class, mock_order_service, mock_risk_action_repository_class):
    """Test that if an order placement fails, the transaction is rolled back."""
    now = datetime.utcnow()
    loser_pg = MockPositionGroupForRisk(
        uuid.uuid4(), "LOSER", 15, "long", PositionGroupStatus.ACTIVE, Decimal("-10.0"), Decimal("-1000"), now - timedelta(hours=1),
        pyramid_count=5, risk_timer_expires=now - timedelta(minutes=1),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    winner_pg1 = MockPositionGroupForRisk(
        uuid.uuid4(), "WINNER1", 15, "long", PositionGroupStatus.ACTIVE, Decimal("5.0"), Decimal("500"), now - timedelta(hours=2),
        weighted_avg_entry=Decimal("100"), total_filled_quantity=Decimal("10")
    )
    
    mock_position_group_repository_class.return_value.get_all.return_value = [loser_pg, winner_pg1]
    
    risk_engine_service.exchange_connector.get_current_price.side_effect = lambda symbol: {
        "LOSER": Decimal("90"),
        "WINNER1": Decimal("150")
    }.get(symbol, Decimal("0"))

    risk_engine_service.exchange_connector.get_precision_rules.return_value = {
        "LOSER": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "WINNER1": {"tick_size": Decimal("0.01"), "step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }

    risk_engine_service.config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-1.0"), 
        require_full_pyramids=True, 
        timer_start_condition="after_all_dca_filled", 
        post_full_wait_minutes=60,
        max_winners_to_combine=3
    )

    # Simulate an order placement failure
    mock_order_service.place_market_order.side_effect = Exception("Order Placement Failed")

    await risk_engine_service._evaluate_positions()

    # The first call to place_market_order should happen, then the exception is raised
    mock_order_service.place_market_order.assert_called_once()
    mock_risk_action_repository_class.return_value.create.assert_not_called() # Risk action should not be created

@pytest.mark.asyncio
async def test_set_risk_blocked_true(risk_engine_service, mock_position_group_repository_class):
    """Test setting risk_blocked to True."""
    group_id = uuid.uuid4()
    mock_pg = MockPositionGroupForRisk(group_id, "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("0"), Decimal("0"), datetime.utcnow())
    mock_position_group_repository_class.return_value.get.return_value = mock_pg

    updated_pg = await risk_engine_service.set_risk_blocked(group_id, True)

    mock_position_group_repository_class.return_value.get.assert_called_once_with(group_id)
    mock_position_group_repository_class.return_value.update.assert_called_once_with(mock_pg)
    assert updated_pg.risk_blocked is True

@pytest.mark.asyncio
async def test_set_risk_blocked_false(risk_engine_service, mock_position_group_repository_class):
    """Test setting risk_blocked to False."""
    group_id = uuid.uuid4()
    mock_pg = MockPositionGroupForRisk(group_id, "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("0"), Decimal("0"), datetime.utcnow(), risk_blocked=True)
    mock_position_group_repository_class.return_value.get.return_value = mock_pg

    updated_pg = await risk_engine_service.set_risk_blocked(group_id, False)

    mock_position_group_repository_class.return_value.get.assert_called_once_with(group_id)
    mock_position_group_repository_class.return_value.update.assert_called_once_with(mock_pg)
    assert updated_pg.risk_blocked is False

@pytest.mark.asyncio
async def test_set_risk_blocked_not_found(risk_engine_service, mock_position_group_repository_class):
    """Test setting risk_blocked for a non-existent PositionGroup raises HTTPException."""
    group_id = uuid.uuid4()
    mock_position_group_repository_class.return_value.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await risk_engine_service.set_risk_blocked(group_id, True)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    mock_position_group_repository_class.return_value.update.assert_not_called()

@pytest.mark.asyncio
async def test_set_risk_skip_once_true(risk_engine_service, mock_position_group_repository_class):
    """Test setting risk_skip_once to True."""
    group_id = uuid.uuid4()
    mock_pg = MockPositionGroupForRisk(group_id, "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("0"), Decimal("0"), datetime.utcnow())
    mock_position_group_repository_class.return_value.get.return_value = mock_pg

    updated_pg = await risk_engine_service.set_risk_skip_once(group_id, True)

    mock_position_group_repository_class.return_value.get.assert_called_once_with(group_id)
    mock_position_group_repository_class.return_value.update.assert_called_once_with(mock_pg)
    assert updated_pg.risk_skip_once is True

@pytest.mark.asyncio
async def test_set_risk_skip_once_false(risk_engine_service, mock_position_group_repository_class):
    """Test setting risk_skip_once to False."""
    group_id = uuid.uuid4()
    mock_pg = MockPositionGroupForRisk(group_id, "BTCUSDT", 15, "long", PositionGroupStatus.ACTIVE, Decimal("0"), Decimal("0"), datetime.utcnow(), risk_skip_once=True)
    mock_position_group_repository_class.return_value.get.return_value = mock_pg

    updated_pg = await risk_engine_service.set_risk_skip_once(group_id, False)

    mock_position_group_repository_class.return_value.get.assert_called_once_with(group_id)
    mock_position_group_repository_class.return_value.update.assert_called_once_with(mock_pg)
    assert updated_pg.risk_skip_once is False

@pytest.mark.asyncio
async def test_set_risk_skip_once_not_found(risk_engine_service, mock_position_group_repository_class):
    """Test setting risk_skip_once for a non-existent PositionGroup raises HTTPException."""
    group_id = uuid.uuid4()
    mock_position_group_repository_class.return_value.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await risk_engine_service.set_risk_skip_once(group_id, True)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    mock_position_group_repository_class.return_value.update.assert_not_called()
