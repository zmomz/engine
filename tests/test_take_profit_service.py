
import pytest
from decimal import Decimal
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder, OrderStatus
from app.services.take_profit_service import check_take_profit_conditions, is_tp_reached

# --- Fixtures ---

@pytest.fixture
def long_position_group():
    """A long position group fixture."""
    pg = PositionGroup(
        id="pg_long",
        symbol="BTCUSDT",
        side="long",
        status="active",
        weighted_avg_entry=Decimal("50000"),
        tp_aggregate_percent=Decimal("2.0")
    )
    pg.dca_orders = []
    return pg

@pytest.fixture
def short_position_group():
    """A short position group fixture."""
    pg = PositionGroup(
        id="pg_short",
        symbol="BTCUSDT",
        side="short",
        status="active",
        weighted_avg_entry=Decimal("50000"),
        tp_aggregate_percent=Decimal("2.0")
    )
    pg.dca_orders = []
    return pg

def create_dca_order(id: str, status: OrderStatus, tp_price: str, tp_hit: bool = False, avg_fill_price: str = None, tp_percent: str = None) -> DCAOrder:
    """Helper to create a DCAOrder instance."""
    return DCAOrder(
        id=id,
        status=status,
        tp_price=Decimal(tp_price),
        tp_hit=tp_hit,
        avg_fill_price=Decimal(avg_fill_price) if avg_fill_price else None,
        tp_percent=Decimal(tp_percent) if tp_percent else None
    )

# --- Tests for is_tp_reached (Step 5) ---

def test_is_tp_reached_long_uses_avg_fill_price():
    """
    Tests that is_tp_reached calculates TP based on the actual avg_fill_price,
    not the pre-calculated tp_price.
    """
    # Pre-calculated TP was based on a planned price of 50000 (tp_price=50500)
    # But the order filled at 49000 due to slippage.
    order = create_dca_order(
        "dca1", OrderStatus.FILLED, 
        tp_price="50500", # Stale TP price
        avg_fill_price="49000", # Actual fill price
        tp_percent="1.0" # 1% TP
    )
    
    # The new TP target should be 49000 * 1.01 = 49490
    current_price_hit = Decimal("49500")
    current_price_miss = Decimal("49400")
    
    assert is_tp_reached(order, current_price_hit, "long") is True
    assert is_tp_reached(order, current_price_miss, "long") is False


# --- Tests for per_leg mode ---

@pytest.mark.asyncio
async def test_per_leg_long_one_leg_hit(long_position_group):
    long_position_group.tp_mode = "per_leg"
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "50500", avg_fill_price="50000", tp_percent="1.0")
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "51000", avg_fill_price="50500", tp_percent="1.0")
    dca3 = create_dca_order("dca3", OrderStatus.OPEN, "50200")
    long_position_group.dca_orders = [dca1, dca2, dca3]
    
    orders_to_close = await check_take_profit_conditions(long_position_group, Decimal("50600"))
    
    assert len(orders_to_close) == 1
    assert orders_to_close[0].id == "dca1"

@pytest.mark.asyncio
async def test_per_leg_long_no_leg_hit(long_position_group):
    long_position_group.tp_mode = "per_leg"
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "50500", avg_fill_price="50000", tp_percent="1.0")
    long_position_group.dca_orders = [dca1]
    
    orders_to_close = await check_take_profit_conditions(long_position_group, Decimal("50400"))
    
    assert len(orders_to_close) == 0

@pytest.mark.asyncio
async def test_per_leg_short_one_leg_hit(short_position_group):
    short_position_group.tp_mode = "per_leg"
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "49500", avg_fill_price="50000", tp_percent="1.0")
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "49000", avg_fill_price="49500", tp_percent="1.0")
    short_position_group.dca_orders = [dca1, dca2]
    
    orders_to_close = await check_take_profit_conditions(short_position_group, Decimal("49400"))
    
    assert len(orders_to_close) == 1
    assert orders_to_close[0].id == "dca1"

# --- Tests for aggregate mode ---

@pytest.mark.asyncio
async def test_aggregate_long_tp_hit(long_position_group):
    long_position_group.tp_mode = "aggregate"
    # Aggregate TP price is 50000 * (1 + 2/100) = 51000
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "50500")
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "51500")
    dca3 = create_dca_order("dca3", OrderStatus.OPEN, "50200")
    long_position_group.dca_orders = [dca1, dca2, dca3]
    
    orders_to_close = await check_take_profit_conditions(long_position_group, Decimal("51100"))
    
    assert len(orders_to_close) == 2
    assert {o.id for o in orders_to_close} == {"dca1", "dca2"}

@pytest.mark.asyncio
async def test_aggregate_long_tp_not_hit(long_position_group):
    long_position_group.tp_mode = "aggregate"
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "50500")
    long_position_group.dca_orders = [dca1]
    
    orders_to_close = await check_take_profit_conditions(long_position_group, Decimal("50900"))
    
    assert len(orders_to_close) == 0

@pytest.mark.asyncio
async def test_aggregate_short_tp_hit(short_position_group):
    short_position_group.tp_mode = "aggregate"
    # Aggregate TP price is 50000 * (1 - 2/100) = 49000
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "49500")
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "48500")
    short_position_group.dca_orders = [dca1, dca2]
    
    orders_to_close = await check_take_profit_conditions(short_position_group, Decimal("48900"))
    
    assert len(orders_to_close) == 2
    assert {o.id for o in orders_to_close} == {"dca1", "dca2"}

# --- Tests for hybrid mode ---

@pytest.mark.asyncio
async def test_hybrid_long_per_leg_triggers_first(long_position_group):
    long_position_group.tp_mode = "hybrid"
    # Aggregate TP is 51000
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "50500", avg_fill_price="50000", tp_percent="1.0") # This leg's TP is 50500
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "51500", avg_fill_price="51000", tp_percent="1.0")
    long_position_group.dca_orders = [dca1, dca2]
    
    # Price hits dca1's TP but not the aggregate TP
    orders_to_close = await check_take_profit_conditions(long_position_group, Decimal("50600"))
    
    assert len(orders_to_close) == 1
    assert orders_to_close[0].id == "dca1"

@pytest.mark.asyncio
async def test_hybrid_long_aggregate_triggers_first(long_position_group):
    long_position_group.tp_mode = "hybrid"
    # Aggregate TP is 51000
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "51200", avg_fill_price="50200", tp_percent="2.0") # TP is 51204
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "51500", avg_fill_price="50800", tp_percent="2.0") # TP is 51816
    long_position_group.dca_orders = [dca1, dca2]
    
    # Price hits aggregate TP but not individual leg TPs
    orders_to_close = await check_take_profit_conditions(long_position_group, Decimal("51100"))
    
    assert len(orders_to_close) == 2
    assert {o.id for o in orders_to_close} == {"dca1", "dca2"}

@pytest.mark.asyncio
async def test_hybrid_short_per_leg_triggers_first(short_position_group):
    short_position_group.tp_mode = "hybrid"
    # Aggregate TP is 49000
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "49500", avg_fill_price="50000", tp_percent="1.0") # TP is 49500
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "48500", avg_fill_price="49000", tp_percent="1.0")
    short_position_group.dca_orders = [dca1, dca2]
    
    # Price hits dca1's TP but not the aggregate TP
    orders_to_close = await check_take_profit_conditions(short_position_group, Decimal("49400"))
    
    assert len(orders_to_close) == 1
    assert orders_to_close[0].id == "dca1"

@pytest.mark.asyncio
async def test_hybrid_short_aggregate_triggers_first(short_position_group):
    short_position_group.tp_mode = "hybrid"
    # Aggregate TP is 49000
    # We set individual TPs lower (higher %) so they don't trigger
    dca1 = create_dca_order("dca1", OrderStatus.FILLED, "48800", avg_fill_price="50000", tp_percent="2.5") # TP is 48750
    dca2 = create_dca_order("dca2", OrderStatus.FILLED, "48500", avg_fill_price="49500", tp_percent="2.5") # TP is 48262.5
    short_position_group.dca_orders = [dca1, dca2]
    
    # Price hits aggregate TP (49000) but not individual leg TPs
    orders_to_close = await check_take_profit_conditions(short_position_group, Decimal("48900"))
    
    assert len(orders_to_close) == 2
    assert {o.id for o in orders_to_close} == {"dca1", "dca2"}
