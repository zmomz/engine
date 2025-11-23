import pytest
from decimal import Decimal
import uuid
from datetime import datetime, timedelta

from app.services.queue_manager import calculate_queue_priority
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup, PositionGroupStatus

# --- Fixtures ---

@pytest.fixture
def user_id_common():
    return uuid.uuid4()

@pytest.fixture
def sample_queued_signal(user_id_common):
    return QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_common,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("50000"),
        signal_payload={},
        queued_at=datetime.utcnow() - timedelta(minutes=5),
        replacement_count=0,
        status=QueueStatus.QUEUED
    )

@pytest.fixture
def active_position_group(user_id_common):
    return PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_common,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        base_entry_price=Decimal("49000"),
        weighted_avg_entry=Decimal("49500"),
        total_dca_legs=5
    )

@pytest.fixture
def active_position_group_different_symbol(user_id_common):
    return PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_common,
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        base_entry_price=Decimal("3000"),
        weighted_avg_entry=Decimal("3050"),
        total_dca_legs=5
    )

# --- Tests for calculate_queue_priority (Tier 1: Pyramid continuation) ---

def test_calculate_priority_pyramid_continuation(sample_queued_signal, active_position_group):
    """
    Test that a pyramid continuation signal gets the highest priority.
    """
    active_groups = [active_position_group]
    priority = calculate_queue_priority(sample_queued_signal, active_groups)
    
    # Expected score: 10,000,000 + tie-breakers
    # Base for pyramid is 10,000,000
    assert priority > Decimal("10000000.0")

# --- Tests for calculate_queue_priority (Tier 2: Deepest current loss percentage) ---

def test_calculate_priority_deepest_loss_percentage(sample_queued_signal):
    """
    Test that a signal with a deeper loss percentage gets higher priority.
    """
    # No active groups, so Tier 1 is skipped
    active_groups = []
    
    signal_deep_loss = sample_queued_signal
    signal_deep_loss.current_loss_percent = Decimal("-5.0") # 5% loss
    
    signal_shallow_loss = QueuedSignal(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("3000"),
        signal_payload={},
        queued_at=datetime.utcnow() - timedelta(minutes=5),
        replacement_count=0,
        status=QueueStatus.QUEUED,
        current_loss_percent=Decimal("-2.0") # 2% loss
    )
    
    priority_deep = calculate_queue_priority(signal_deep_loss, active_groups)
    priority_shallow = calculate_queue_priority(signal_shallow_loss, active_groups)
    
    # Expected score: 1,000,000 + (abs(loss_percent) * 10000)
    # Plus time_in_queue_score (5 minutes * 0.001 = 0.3)
    
    # We check relative order first
    assert priority_deep > priority_shallow
    
    # Check approximate values (ignoring time_in_queue small variations)
    # Base: 1,000,000
    # Deep loss score: 5.0 * 10000 = 50,000
    # Shallow loss score: 2.0 * 10000 = 20,000
    
    assert priority_deep > Decimal("1050000.0") 
    assert priority_shallow > Decimal("1020000.0")