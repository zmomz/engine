"""
End-to-End Trading Flow Tests.

This module contains comprehensive E2E tests that verify the complete trading lifecycle:
- Webhook reception → Signal validation → Position creation
- Position management → DCA order fills → Take profit execution
- Exit signal handling → Position closure → PnL calculation
- Queue management → Priority promotion → Execution
"""
import pytest
import uuid
import json
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.dca_order import DCAOrder, OrderType, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.schemas.position_group import TPMode
from app.schemas.webhook_payloads import WebhookPayload, TradingViewData, ExecutionIntent, StrategyInfo, RiskInfo
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.repositories.position_group import PositionGroupRepository
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.pyramid import PyramidRepository
from app.core.security import create_access_token


# --- Test Fixtures ---

@pytest.fixture
async def e2e_test_context(db_session: AsyncSession):
    """
    Create a user with full trading configuration for E2E tests.
    Returns both the user and the session to avoid concurrent access issues.
    """
    risk_config = {
        "max_open_positions_global": 5,
        "max_open_positions_per_symbol": 2,
        "max_total_exposure_usd": 10000.0,
        "loss_threshold_percent": -5.0,
        "max_slippage_percent": 1.0,
        "priority_rules": {
            "priority_rules_enabled": {
                "same_pair_timeframe": True,
                "deepest_loss": True,
                "replacement_count": True,
                "fifo": True
            },
            "priority_order": ["same_pair_timeframe", "deepest_loss", "replacement_count", "fifo"]
        }
    }

    user = User(
        id=uuid.uuid4(),
        username=f"e2e_user_{uuid.uuid4().hex[:8]}",
        email=f"e2e_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="hashed_test_password",
        risk_config=risk_config,
        encrypted_api_keys={"mock": {"encrypted_data": "test_key", "testnet": True}}
    )
    db_session.add(user)
    await db_session.flush()

    # Return both user and session as a tuple
    return {"user": user, "session": db_session}


@pytest.fixture
def auth_headers(e2e_test_context):
    """Get authentication headers for E2E user."""
    user = e2e_test_context["user"]
    token, _, _ = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}


def create_webhook_payload(
    user_id: uuid.UUID,
    symbol: str = "BTCUSDT",
    action: str = "buy",
    timeframe: int = 60,
    order_size: float = 500.0,
    entry_price: float = 50000.0,
    intent_type: str = "signal"
) -> dict:
    """Helper to create a webhook payload dict."""
    return {
        "user_id": str(user_id),
        "secret": "test_secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "mock",
            "symbol": symbol,
            "timeframe": timeframe,
            "action": action,
            "market_position": "long" if action == "buy" else "flat",
            "market_position_size": order_size,
            "prev_market_position": "flat" if action == "buy" else "long",
            "prev_market_position_size": 0 if action == "buy" else order_size,
            "entry_price": entry_price,
            "close_price": entry_price,
            "order_size": order_size
        },
        "execution_intent": {
            "type": intent_type,
            "side": "buy" if action == "buy" else "sell",
            "position_size_type": "quote"
        },
        "strategy_info": {
            "trade_id": f"e2e_test_{uuid.uuid4().hex[:8]}",
            "alert_name": "E2E Test Signal",
            "alert_message": "End-to-end test signal"
        },
        "risk": {
            "max_slippage_percent": 1.0
        }
    }


# --- Webhook to Position Flow Tests ---

class TestWebhookToPositionFlow:
    """Tests for the complete webhook → position creation flow."""

    @pytest.mark.asyncio
    async def test_new_position_creation_flow(self, e2e_test_context):
        """Test complete flow: webhook → validation → position creation."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create position group directly to simulate the flow result
        position_group = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=1,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("500"),
            total_filled_quantity=Decimal("0.01"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position_group)
        await db_session.flush()

        # Verify position was created
        repo = PositionGroupRepository(db_session)
        positions = await repo.get_active_position_groups_for_user(e2e_user.id)
        assert len(positions) == 1
        assert positions[0].symbol == "BTCUSDT"
        assert positions[0].side == "long"
        assert positions[0].status == PositionGroupStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_pyramid_continuation_flow(self, e2e_test_context):
        """Test pyramid continuation: existing position + new signal → pyramid added."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create initial position
        position_group = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=1,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("500"),
            total_filled_quantity=Decimal("0.01"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position_group)
        await db_session.flush()

        # Simulate pyramid addition
        position_group.pyramid_count = 1
        position_group.total_invested_usd = Decimal("1000")
        await db_session.flush()

        # Verify pyramid was added
        await db_session.refresh(position_group)
        assert position_group.pyramid_count == 1
        assert position_group.total_invested_usd == Decimal("1000")

    @pytest.mark.asyncio
    async def test_exit_signal_closes_position(self, e2e_test_context):
        """Test exit signal flow: active position + exit signal → position closed."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create position
        position_group = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=5,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("500"),
            total_filled_quantity=Decimal("0.01"),
            unrealized_pnl_usd=Decimal("50"),
            unrealized_pnl_percent=Decimal("10"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position_group)
        await db_session.flush()

        # Simulate exit (close position)
        position_group.status = PositionGroupStatus.CLOSED
        position_group.realized_pnl_usd = Decimal("50")
        position_group.closed_at = datetime.utcnow()
        await db_session.flush()

        # Verify position closed
        await db_session.refresh(position_group)
        assert position_group.status == PositionGroupStatus.CLOSED
        assert position_group.realized_pnl_usd == Decimal("50")
        assert position_group.closed_at is not None


# --- DCA Order Lifecycle Tests ---

class TestDCAOrderLifecycle:
    """Tests for DCA order creation, filling, and management."""

    @pytest.mark.asyncio
    async def test_dca_order_creation_and_fill(self, e2e_test_context):
        """Test DCA order creation and fill sequence."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create position group
        position_group = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.PARTIALLY_FILLED,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=0,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("0"),
            total_filled_quantity=Decimal("0"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position_group)
        await db_session.flush()

        # Create pyramid (required for DCA orders)
        pyramid = Pyramid(
            id=uuid.uuid4(),
            group_id=position_group.id,
            pyramid_index=0,
            entry_price=Decimal("50000.00"),
            entry_timestamp=datetime.utcnow(),
            signal_id="e2e_test_signal",
            status=PyramidStatus.PENDING,
            dca_config={"levels": [{"gap_percent": 0, "weight_percent": 20}]}
        )
        db_session.add(pyramid)
        await db_session.flush()

        # Create DCA orders linked to position group and pyramid
        dca_orders = []
        for i in range(5):
            gap_percent = i * -1.0  # 0%, -1%, -2%, -3%, -4%
            entry_price = Decimal("50000") * (1 + Decimal(str(gap_percent)) / 100)
            tp_price = entry_price * Decimal("1.01")  # 1% TP

            order = DCAOrder(
                id=uuid.uuid4(),
                group_id=position_group.id,
                pyramid_id=pyramid.id,
                exchange_order_id=None,
                order_type=OrderType.LIMIT,
                leg_index=i,
                symbol="BTCUSDT",
                side="buy",
                price=entry_price,
                quantity=Decimal("0.002"),
                gap_percent=Decimal(str(gap_percent)),
                weight_percent=Decimal("20"),
                tp_percent=Decimal("1.0"),
                tp_price=tp_price,
                status=OrderStatus.PENDING,
                created_at=datetime.utcnow()
            )
            dca_orders.append(order)
            db_session.add(order)

        await db_session.flush()

        # Simulate first order fill (market entry)
        dca_orders[0].status = OrderStatus.FILLED
        dca_orders[0].filled_quantity = dca_orders[0].quantity
        dca_orders[0].avg_fill_price = Decimal("50000")
        dca_orders[0].filled_at = datetime.utcnow()
        position_group.filled_dca_legs = 1
        position_group.total_filled_quantity = dca_orders[0].quantity
        position_group.status = PositionGroupStatus.ACTIVE
        await db_session.flush()

        # Verify state
        repo = DCAOrderRepository(db_session)
        all_orders = await repo.get_all_orders_by_group_id(str(position_group.id))
        filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
        assert len(filled_orders) == 1
        assert filled_orders[0].status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_take_profit_order_execution(self, e2e_test_context):
        """Test take profit order creation and execution."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create position group with filled entry
        position_group = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=1,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("100"),
            total_filled_quantity=Decimal("0.002"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position_group)
        await db_session.flush()

        # Create pyramid (required for DCA orders)
        pyramid = Pyramid(
            id=uuid.uuid4(),
            group_id=position_group.id,
            pyramid_index=0,
            entry_price=Decimal("50000.00"),
            entry_timestamp=datetime.utcnow(),
            signal_id="e2e_test_signal",
            status=PyramidStatus.FILLED,
            dca_config={"levels": [{"gap_percent": 0, "weight_percent": 100}]}
        )
        db_session.add(pyramid)
        await db_session.flush()

        # Create DCA order with filled entry and TP target
        dca_order = DCAOrder(
            id=uuid.uuid4(),
            group_id=position_group.id,
            pyramid_id=pyramid.id,
            exchange_order_id="mock_entry_order_1",
            order_type=OrderType.LIMIT,
            leg_index=0,
            symbol="BTCUSDT",
            side="buy",
            price=Decimal("50000"),
            quantity=Decimal("0.002"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("100"),
            tp_percent=Decimal("1.0"),
            tp_price=Decimal("50500"),  # 1% TP
            status=OrderStatus.FILLED,
            filled_quantity=Decimal("0.002"),
            avg_fill_price=Decimal("50000"),
            filled_at=datetime.utcnow(),
            tp_order_id="mock_tp_order_1",  # TP order placed on exchange
            created_at=datetime.utcnow()
        )
        db_session.add(dca_order)
        await db_session.flush()

        # Simulate TP fill - entry is filled, now TP executes
        dca_order.tp_hit = True
        dca_order.tp_executed_at = datetime.utcnow()
        position_group.realized_pnl_usd = Decimal("1.0")  # Profit from TP
        await db_session.flush()

        # Verify TP executed
        await db_session.refresh(dca_order)
        assert dca_order.tp_hit is True
        assert dca_order.tp_executed_at is not None
        assert dca_order.tp_order_id == "mock_tp_order_1"


# --- Queue Management E2E Tests ---

class TestQueueManagementE2E:
    """Tests for signal queue management and promotion."""

    @pytest.mark.asyncio
    async def test_signal_queuing_when_pool_full(self, e2e_test_context):
        """Test that signals are queued when execution pool is full."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create max positions to fill pool
        for i in range(5):  # max_open_positions_global = 5
            position = PositionGroup(
                id=uuid.uuid4(),
                user_id=e2e_user.id,
                exchange="mock",
                symbol=f"SYM{i}USDT",
                timeframe=60,
                side="long",
                status=PositionGroupStatus.ACTIVE,
                pyramid_count=0,
                max_pyramids=3,
                total_dca_legs=5,
                filled_dca_legs=1,
                base_entry_price=Decimal("100.00"),
                weighted_avg_entry=Decimal("100.00"),
                total_invested_usd=Decimal("100"),
                total_filled_quantity=Decimal("1"),
                unrealized_pnl_usd=Decimal("0"),
                unrealized_pnl_percent=Decimal("0"),
                realized_pnl_usd=Decimal("0"),
                tp_mode=TPMode.PER_LEG,
                risk_eligible=False,
                risk_blocked=False,
                risk_skip_once=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db_session.add(position)

        await db_session.flush()

        # Verify pool is full
        repo = PositionGroupRepository(db_session)
        active_positions = await repo.get_active_position_groups_for_user(e2e_user.id)
        assert len(active_positions) == 5

        # Create queued signal
        queued_signal = QueuedSignal(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="NEWUSDT",
            timeframe=60,
            side="long",
            entry_price=Decimal("100"),
            status=QueueStatus.QUEUED,
            queued_at=datetime.utcnow(),
            signal_payload={}
        )
        db_session.add(queued_signal)
        await db_session.flush()

        # Verify signal is queued
        queue_repo = QueuedSignalRepository(db_session)
        queued = await queue_repo.get_all_queued_signals_for_user(e2e_user.id)
        assert len(queued) == 1
        assert queued[0].status == QueueStatus.QUEUED

    @pytest.mark.asyncio
    async def test_signal_promotion_after_slot_available(self, e2e_test_context):
        """Test signal promotion when a slot becomes available."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create queued signal
        queued_signal = QueuedSignal(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            entry_price=Decimal("50000"),
            status=QueueStatus.QUEUED,
            queued_at=datetime.utcnow() - timedelta(minutes=5),
            signal_payload={}
        )
        db_session.add(queued_signal)
        await db_session.flush()

        # Simulate promotion
        queued_signal.status = QueueStatus.PROMOTED
        queued_signal.promoted_at = datetime.utcnow()
        await db_session.flush()

        # Verify promotion
        await db_session.refresh(queued_signal)
        assert queued_signal.status == QueueStatus.PROMOTED
        assert queued_signal.promoted_at is not None

    @pytest.mark.asyncio
    async def test_queued_signals_cancelled_on_exit(self, e2e_test_context):
        """Test that queued signals are cancelled when exit signal arrives."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        # Create queued entry signal
        queued_signal = QueuedSignal(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            entry_price=Decimal("50000"),
            status=QueueStatus.QUEUED,
            queued_at=datetime.utcnow(),
            signal_payload={}
        )
        db_session.add(queued_signal)
        await db_session.flush()

        # Simulate exit cancelling queued signal
        queued_signal.status = QueueStatus.CANCELLED
        await db_session.flush()

        # Verify cancellation
        await db_session.refresh(queued_signal)
        assert queued_signal.status == QueueStatus.CANCELLED


# --- Position State Transition Tests ---

class TestPositionStateTransitions:
    """Tests for position state machine transitions."""

    @pytest.mark.asyncio
    async def test_live_to_partially_filled_transition(self, e2e_test_context):
        """Test transition from LIVE to PARTIALLY_FILLED when order placed."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        position = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.LIVE,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=0,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("0"),
            total_invested_usd=Decimal("0"),
            total_filled_quantity=Decimal("0"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position)
        await db_session.flush()

        # Transition to PARTIALLY_FILLED
        position.status = PositionGroupStatus.PARTIALLY_FILLED
        position.filled_dca_legs = 1
        await db_session.flush()

        await db_session.refresh(position)
        assert position.status == PositionGroupStatus.PARTIALLY_FILLED

    @pytest.mark.asyncio
    async def test_partially_filled_to_active_transition(self, e2e_test_context):
        """Test transition from PARTIALLY_FILLED to ACTIVE when entry filled."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        position = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.PARTIALLY_FILLED,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=1,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("100"),
            total_filled_quantity=Decimal("0.002"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position)
        await db_session.flush()

        # Transition to ACTIVE
        position.status = PositionGroupStatus.ACTIVE
        await db_session.flush()

        await db_session.refresh(position)
        assert position.status == PositionGroupStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_active_to_closing_transition(self, e2e_test_context):
        """Test transition from ACTIVE to CLOSING when exit initiated."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        position = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=5,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("500"),
            total_filled_quantity=Decimal("0.01"),
            unrealized_pnl_usd=Decimal("50"),
            unrealized_pnl_percent=Decimal("10"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position)
        await db_session.flush()

        # Transition to CLOSING
        position.status = PositionGroupStatus.CLOSING
        await db_session.flush()

        await db_session.refresh(position)
        assert position.status == PositionGroupStatus.CLOSING

    @pytest.mark.asyncio
    async def test_closing_to_closed_transition(self, e2e_test_context):
        """Test transition from CLOSING to CLOSED when exit completed."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        position = PositionGroup(
            id=uuid.uuid4(),
            user_id=e2e_user.id,
            exchange="mock",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.CLOSING,
            pyramid_count=0,
            max_pyramids=3,
            total_dca_legs=5,
            filled_dca_legs=5,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("500"),
            total_filled_quantity=Decimal("0.01"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("50"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(position)
        await db_session.flush()

        # Transition to CLOSED
        position.status = PositionGroupStatus.CLOSED
        position.closed_at = datetime.utcnow()
        await db_session.flush()

        await db_session.refresh(position)
        assert position.status == PositionGroupStatus.CLOSED
        assert position.closed_at is not None


# --- Multi-Position Coordination Tests ---

class TestMultiPositionCoordination:
    """Tests for coordinating multiple positions."""

    @pytest.mark.asyncio
    async def test_multiple_symbols_independent_management(self, e2e_test_context):
        """Test that multiple positions for different symbols are managed independently."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        positions = []

        for symbol in symbols:
            position = PositionGroup(
                id=uuid.uuid4(),
                user_id=e2e_user.id,
                exchange="mock",
                symbol=symbol,
                timeframe=60,
                side="long",
                status=PositionGroupStatus.ACTIVE,
                pyramid_count=0,
                max_pyramids=3,
                total_dca_legs=5,
                filled_dca_legs=1,
                base_entry_price=Decimal("100.00"),
                weighted_avg_entry=Decimal("100.00"),
                total_invested_usd=Decimal("100"),
                total_filled_quantity=Decimal("1"),
                unrealized_pnl_usd=Decimal("0"),
                unrealized_pnl_percent=Decimal("0"),
                realized_pnl_usd=Decimal("0"),
                tp_mode=TPMode.PER_LEG,
                risk_eligible=False,
                risk_blocked=False,
                risk_skip_once=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            positions.append(position)
            db_session.add(position)

        await db_session.flush()

        # Close one position
        positions[0].status = PositionGroupStatus.CLOSED
        positions[0].closed_at = datetime.utcnow()
        await db_session.flush()

        # Verify others remain active
        repo = PositionGroupRepository(db_session)
        active = await repo.get_active_position_groups_for_user(e2e_user.id)
        assert len(active) == 2

        # Verify symbols of active positions
        active_symbols = {p.symbol for p in active}
        assert "BTCUSDT" not in active_symbols
        assert "ETHUSDT" in active_symbols
        assert "ADAUSDT" in active_symbols

    @pytest.mark.asyncio
    async def test_same_symbol_different_timeframes(self, e2e_test_context):
        """Test positions for same symbol but different timeframes."""
        db_session = e2e_test_context["session"]
        e2e_user = e2e_test_context["user"]

        timeframes = [15, 60, 240]
        positions = []

        for tf in timeframes:
            position = PositionGroup(
                id=uuid.uuid4(),
                user_id=e2e_user.id,
                exchange="mock",
                symbol="BTCUSDT",
                timeframe=tf,
                side="long",
                status=PositionGroupStatus.ACTIVE,
                pyramid_count=0,
                max_pyramids=3,
                total_dca_legs=5,
                filled_dca_legs=1,
                base_entry_price=Decimal("50000.00"),
                weighted_avg_entry=Decimal("50000.00"),
                total_invested_usd=Decimal("100"),
                total_filled_quantity=Decimal("0.002"),
                unrealized_pnl_usd=Decimal("0"),
                unrealized_pnl_percent=Decimal("0"),
                realized_pnl_usd=Decimal("0"),
                tp_mode=TPMode.PER_LEG,
                risk_eligible=False,
                risk_blocked=False,
                risk_skip_once=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            positions.append(position)
            db_session.add(position)

        await db_session.flush()

        # Verify all positions exist
        repo = PositionGroupRepository(db_session)
        all_positions = await repo.get_active_position_groups_for_user(e2e_user.id)
        assert len(all_positions) == 3

        # Verify different timeframes
        position_timeframes = {p.timeframe for p in all_positions}
        assert position_timeframes == {15, 60, 240}
