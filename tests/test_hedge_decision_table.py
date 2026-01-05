"""
Hedge Execution Decision Table Tests

Decision Table Testing Standard:
Each row in the decision table is a test case with specific conditions and expected outcomes.

Conditions:
- C1: Has winning position (unrealized_pnl > 0)
- C2: Has losing position (unrealized_pnl < 0)
- C3: Risk timer expired (current_time > risk_timer_expires)
- C4: Risk eligible (risk_eligible = True)
- C5: Offset amount > min threshold

Actions:
- A1: Execute hedge (partial close of winner to offset loser loss)
- A2: Cancel winner's open orders
- A3: Update order statuses to CANCELLED
- A4: Update position quantities
- A5: Record risk action

This tests the "after hedge" bug scenario where order status was incorrect after hedge execution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User
from app.services.risk.risk_engine import RiskEngineService
from app.schemas.grid_config import RiskEngineConfig


@pytest.fixture
def risk_config():
    """Standard risk configuration for tests."""
    return RiskEngineConfig(
        enabled=True,
        evaluation_interval_seconds=60,
        hedge_threshold_percent=Decimal("2.0"),
        grace_period_minutes=5,
        min_winner_profit_percent=Decimal("1.0"),
        max_offset_per_action_percent=Decimal("50.0"),
        daily_loss_limit_usd=Decimal("1000.0"),
        min_offset_amount_usd=Decimal("10.0")
    )


@pytest.fixture
def mock_user():
    """Mock user with API keys."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "test_user"
    user.encrypted_api_keys = {"binance": {"encrypted_data": "test_key"}}
    return user


@pytest.fixture
def mock_loser():
    """Mock losing position."""
    loser = MagicMock(spec=PositionGroup)
    loser.id = uuid.uuid4()
    loser.symbol = "BTCUSDT"
    loser.exchange = "binance"
    loser.side = "long"
    loser.status = PositionGroupStatus.ACTIVE.value
    loser.unrealized_pnl_usd = Decimal("-100")
    loser.unrealized_pnl_percent = Decimal("-5")
    loser.total_filled_quantity = Decimal("0.01")
    loser.total_invested_usd = Decimal("2000")
    loser.weighted_avg_entry = Decimal("50000")
    loser.risk_skip_once = False
    loser.risk_blocked = False
    loser.risk_eligible = True
    loser.risk_timer_expires = datetime.utcnow() - timedelta(minutes=10)  # Expired
    return loser


@pytest.fixture
def mock_winner():
    """Mock winning position."""
    winner = MagicMock(spec=PositionGroup)
    winner.id = uuid.uuid4()
    winner.symbol = "ETHUSDT"
    winner.exchange = "binance"
    winner.side = "long"
    winner.status = PositionGroupStatus.ACTIVE.value
    winner.unrealized_pnl_usd = Decimal("200")
    winner.unrealized_pnl_percent = Decimal("10")
    winner.total_filled_quantity = Decimal("1.0")
    winner.total_invested_usd = Decimal("2000")
    winner.weighted_avg_entry = Decimal("2000")
    winner.total_hedged_qty = Decimal("0")
    winner.total_hedged_value_usd = Decimal("0")
    winner.risk_eligible = True
    return winner


class TestHedgeDecisionTable:
    """
    Decision table for hedge execution.

    | Test Case | C1 (Winner) | C2 (Loser) | C3 (Timer) | C4 (Eligible) | Expected |
    |-----------|-------------|------------|------------|---------------|----------|
    | 1         | Y           | Y          | Y          | Y             | Execute  |
    | 2         | N           | Y          | Y          | Y             | Skip     |
    | 3         | Y           | N          | Y          | Y             | Skip     |
    | 4         | Y           | Y          | N          | Y             | Skip     |
    | 5         | Y           | Y          | Y          | N             | Skip     |
    """

    @pytest.mark.asyncio
    async def test_case_1_all_conditions_met_execute_hedge(
        self, risk_config, mock_user, mock_loser, mock_winner
    ):
        """
        C1=Y, C2=Y, C3=Y, C4=Y -> Execute hedge

        All conditions met: should execute hedge, cancel orders, update statuses.
        """
        session = AsyncMock()
        loser_pyramid_id = uuid.uuid4()
        winner_pyramid_id = uuid.uuid4()

        # Create pyramids
        loser_pyramid = MagicMock()
        loser_pyramid.id = loser_pyramid_id
        loser_pyramid.group_id = mock_loser.id

        winner_pyramid = MagicMock()
        winner_pyramid.id = winner_pyramid_id
        winner_pyramid.group_id = mock_winner.id

        # Mock session.execute for pyramid queries
        execute_call_count = [0]
        async def mock_execute(query):
            result = MagicMock()
            if execute_call_count[0] == 0:
                result.scalar_one_or_none.return_value = loser_pyramid
            else:
                result.scalar_one_or_none.return_value = winner_pyramid
            execute_call_count[0] += 1
            return result
        session.execute = mock_execute

        # Mock repositories
        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_loser, mock_winner])
        mock_pos_repo.update = AsyncMock()

        mock_risk_repo = MagicMock()
        mock_risk_repo.create = AsyncMock()

        mock_order_service = MagicMock()
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.place_market_order = AsyncMock()
        mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()

        mock_exchange = AsyncMock()
        mock_exchange.get_precision_rules = AsyncMock(return_value={})
        # Return prices that result in correct PnL values after _refresh_positions_pnl:
        # BTCUSDT (loser): entry=50000, qty=0.01, want loss=-100 -> price=40000
        # ETHUSDT (winner): entry=2000, qty=1.0, want profit=+200 -> price=2200
        async def mock_get_price(symbol):
            if "BTC" in symbol:
                return Decimal("40000")  # (40000-50000)*0.01 = -100
            else:
                return Decimal("2200")   # (2200-2000)*1.0 = +200
        mock_exchange.get_current_price = mock_get_price
        mock_exchange.close = AsyncMock()

        with (
            patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
            patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService,
            patch("app.services.risk.risk_engine.get_exchange_connector") as mock_get_connector,
            patch("app.services.risk.risk_engine.calculate_partial_close_quantities") as mock_calc_close,
            patch("app.services.risk.risk_engine.update_risk_timers", new_callable=AsyncMock),
            patch("app.services.risk.risk_engine.broadcast_risk_event", new_callable=AsyncMock)
        ):
            mock_select.return_value = (mock_loser, [mock_winner], Decimal("100"))
            MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
            mock_get_connector.return_value = mock_exchange
            mock_calc_close.return_value = [(mock_winner, Decimal("0.5"))]

            mock_user.risk_config = risk_config.model_dump()

            service = RiskEngineService(
                session_factory=lambda: session,
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
                dca_order_repository_class=MagicMock(),
                order_service_class=mock_order_service,
                risk_engine_config=risk_config
            )

            await service._evaluate_user_positions(session, mock_user)

            # ASSERTIONS - Verify hedge was executed

            # A1: Market orders placed for both loser (full close) and winner (partial close)
            assert mock_order_service_instance.place_market_order.call_count >= 2, \
                "Hedge should place market orders for loser and winner"

            # A2: Cancel orders was called for loser
            mock_order_service_instance.cancel_open_orders_for_group.assert_called()

            # A5: Risk action was recorded
            mock_risk_repo.create.assert_called_once()

            # Verify risk action has correct data
            risk_action = mock_risk_repo.create.call_args[0][0]
            assert risk_action.group_id == mock_loser.id
            assert risk_action.loser_group_id == mock_loser.id
            # loser_pnl_usd should be the captured value BEFORE position was closed
            # (unrealized_pnl_usd gets reset to 0 when position is closed)
            assert risk_action.loser_pnl_usd == Decimal("-100")

    @pytest.mark.asyncio
    async def test_case_2_no_winner_skip_hedge(self, risk_config, mock_user, mock_loser):
        """
        C1=N, C2=Y, C3=Y, C4=Y -> Skip hedge

        No winner to offset against - should skip hedge.
        """
        session = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_loser])  # Only loser
        mock_pos_repo.update = AsyncMock()

        mock_risk_repo = MagicMock()
        mock_risk_repo.create = AsyncMock()

        mock_order_service = MagicMock()
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.place_market_order = AsyncMock()

        mock_exchange = AsyncMock()
        mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))
        mock_exchange.close = AsyncMock()

        with (
            patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
            patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService,
            patch("app.services.risk.risk_engine.get_exchange_connector") as mock_get_connector,
            patch("app.services.risk.risk_engine.update_risk_timers", new_callable=AsyncMock),
            patch("app.services.risk.risk_engine.broadcast_risk_event", new_callable=AsyncMock)
        ):
            # No winners available
            mock_select.return_value = (mock_loser, [], Decimal("0"))
            mock_get_connector.return_value = mock_exchange
            MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")

            mock_user.risk_config = risk_config.model_dump()

            service = RiskEngineService(
                session_factory=lambda: session,
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
                dca_order_repository_class=MagicMock(),
                order_service_class=mock_order_service,
                risk_engine_config=risk_config
            )

            await service._evaluate_user_positions(session, mock_user)

            # No hedge should be executed
            mock_order_service_instance.place_market_order.assert_not_called()
            mock_risk_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_case_3_no_loser_skip_hedge(self, risk_config, mock_user, mock_winner):
        """
        C1=Y, C2=N, C3=Y, C4=Y -> Skip hedge

        No losing position - nothing to offset.
        """
        session = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_winner])  # Only winner
        mock_pos_repo.update = AsyncMock()

        mock_risk_repo = MagicMock()
        mock_risk_repo.create = AsyncMock()

        mock_order_service = MagicMock()
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.place_market_order = AsyncMock()

        mock_exchange = AsyncMock()
        mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))
        mock_exchange.close = AsyncMock()

        with (
            patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
            patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService,
            patch("app.services.risk.risk_engine.get_exchange_connector") as mock_get_connector,
            patch("app.services.risk.risk_engine.update_risk_timers", new_callable=AsyncMock),
            patch("app.services.risk.risk_engine.broadcast_risk_event", new_callable=AsyncMock)
        ):
            # No loser found
            mock_select.return_value = (None, [mock_winner], Decimal("0"))
            mock_get_connector.return_value = mock_exchange
            MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")

            mock_user.risk_config = risk_config.model_dump()

            service = RiskEngineService(
                session_factory=lambda: session,
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
                dca_order_repository_class=MagicMock(),
                order_service_class=mock_order_service,
                risk_engine_config=risk_config
            )

            await service._evaluate_user_positions(session, mock_user)

            # No hedge should be executed
            mock_order_service_instance.place_market_order.assert_not_called()
            mock_risk_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_case_4_timer_not_expired_skip_hedge(
        self, risk_config, mock_user, mock_loser, mock_winner
    ):
        """
        C1=Y, C2=Y, C3=N, C4=Y -> Skip hedge

        Timer not expired - still in grace period.
        """
        # Set timer to future (not expired)
        mock_loser.risk_timer_expires = datetime.utcnow() + timedelta(minutes=10)
        mock_loser.risk_eligible = False  # Not yet eligible

        session = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_loser, mock_winner])
        mock_pos_repo.update = AsyncMock()

        mock_risk_repo = MagicMock()
        mock_risk_repo.create = AsyncMock()

        mock_order_service = MagicMock()
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.place_market_order = AsyncMock()

        mock_exchange = AsyncMock()
        mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))
        mock_exchange.close = AsyncMock()

        with (
            patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
            patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService,
            patch("app.services.risk.risk_engine.get_exchange_connector") as mock_get_connector,
            patch("app.services.risk.risk_engine.update_risk_timers", new_callable=AsyncMock),
            patch("app.services.risk.risk_engine.broadcast_risk_event", new_callable=AsyncMock)
        ):
            # Loser not eligible yet
            mock_select.return_value = (None, [], Decimal("0"))  # select_loser_and_winners filters by eligibility
            MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")
            mock_get_connector.return_value = mock_exchange

            mock_user.risk_config = risk_config.model_dump()

            service = RiskEngineService(
                session_factory=lambda: session,
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
                dca_order_repository_class=MagicMock(),
                order_service_class=mock_order_service,
                risk_engine_config=risk_config
            )

            await service._evaluate_user_positions(session, mock_user)

            # No hedge - timer not expired
            mock_order_service_instance.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_case_5_not_eligible_skip_hedge(
        self, risk_config, mock_user, mock_loser, mock_winner
    ):
        """
        C1=Y, C2=Y, C3=Y, C4=N -> Skip hedge

        Position not eligible for risk actions (risk_eligible=False).
        """
        mock_loser.risk_eligible = False

        session = AsyncMock()

        mock_pos_repo = MagicMock()
        mock_pos_repo.get_all_active_by_user = AsyncMock(return_value=[mock_loser, mock_winner])
        mock_pos_repo.update = AsyncMock()

        mock_risk_repo = MagicMock()
        mock_risk_repo.create = AsyncMock()

        mock_order_service = MagicMock()
        mock_order_service_instance = mock_order_service.return_value
        mock_order_service_instance.place_market_order = AsyncMock()

        mock_exchange = AsyncMock()
        mock_exchange.get_current_price = AsyncMock(return_value=Decimal("50000"))
        mock_exchange.close = AsyncMock()

        with (
            patch("app.services.risk.risk_engine.select_loser_and_winners") as mock_select,
            patch("app.services.exchange_abstraction.factory.EncryptionService") as MockEncryptionService,
            patch("app.services.risk.risk_engine.get_exchange_connector") as mock_get_connector,
            patch("app.services.risk.risk_engine.update_risk_timers", new_callable=AsyncMock),
            patch("app.services.risk.risk_engine.broadcast_risk_event", new_callable=AsyncMock)
        ):
            # Not eligible - filtered out
            mock_select.return_value = (None, [], Decimal("0"))
            mock_get_connector.return_value = mock_exchange
            MockEncryptionService.return_value.decrypt_keys.return_value = ("key", "secret")

            mock_user.risk_config = risk_config.model_dump()

            service = RiskEngineService(
                session_factory=lambda: session,
                position_group_repository_class=MagicMock(return_value=mock_pos_repo),
                risk_action_repository_class=MagicMock(return_value=mock_risk_repo),
                dca_order_repository_class=MagicMock(),
                order_service_class=mock_order_service,
                risk_engine_config=risk_config
            )

            await service._evaluate_user_positions(session, mock_user)

            # No hedge - not eligible
            mock_order_service_instance.place_market_order.assert_not_called()


class TestAfterHedgeStateVerification:
    """
    Specifically tests the "after hedge" bug where order status was incorrect.

    These tests verify that after hedge execution:
    1. All cancelled orders have status = CANCELLED
    2. filled_quantity is preserved on partial fills
    3. Position quantities are updated correctly
    """

    @pytest.mark.asyncio
    async def test_cancelled_orders_have_correct_status_after_hedge(self):
        """
        After hedge, all cancelled orders must have status=CANCELLED in DB.

        This is the core test for the "after hedge" bug.
        """
        from app.services.order_management import OrderService

        # Setup
        group_id = uuid.uuid4()
        pyramid_id = uuid.uuid4()

        open_order = DCAOrder(
            id=uuid.uuid4(),
            group_id=group_id,
            pyramid_id=pyramid_id,
            leg_index=0,
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("100"),
            tp_percent=Decimal("2"),
            status=OrderStatus.OPEN.value,
            exchange_order_id="EX123",
            filled_quantity=Decimal("0")
        )

        mock_session = AsyncMock()
        mock_connector = AsyncMock()
        mock_connector.cancel_order.return_value = {"status": "canceled"}

        mock_dca_repo = AsyncMock()
        mock_dca_repo.get_all_orders_by_group_id.return_value = [open_order]
        mock_dca_repo.update = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        with (
            patch("app.services.order_management.DCAOrderRepository", return_value=mock_dca_repo),
            patch("app.services.order_management.PositionGroupRepository")
        ):
            service = OrderService(
                session=mock_session,
                user=mock_user,
                exchange_connector=mock_connector
            )

            await service.cancel_open_orders_for_group(group_id)

            # CRITICAL ASSERTION: Order status must be CANCELLED
            assert open_order.status == OrderStatus.CANCELLED.value, \
                "Order status must be CANCELLED after cancel_open_orders_for_group"

            # Verify repository update was called
            mock_dca_repo.update.assert_called()

            # Verify the updated order passed to repository has correct status
            updated_order = mock_dca_repo.update.call_args[0][0]
            assert updated_order.status == OrderStatus.CANCELLED.value, \
                "Updated order passed to repository must have CANCELLED status"

    @pytest.mark.asyncio
    async def test_partially_filled_order_preserves_quantity_on_cancel(self):
        """
        When cancelling a PARTIALLY_FILLED order, filled_quantity must be preserved.
        """
        from app.services.order_management import OrderService

        group_id = uuid.uuid4()
        pyramid_id = uuid.uuid4()

        partial_order = DCAOrder(
            id=uuid.uuid4(),
            group_id=group_id,
            pyramid_id=pyramid_id,
            leg_index=0,
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("100"),
            tp_percent=Decimal("2"),
            status=OrderStatus.PARTIALLY_FILLED.value,
            exchange_order_id="EX123",
            filled_quantity=Decimal("0.05")  # 50% filled
        )

        mock_session = AsyncMock()
        mock_connector = AsyncMock()
        mock_connector.cancel_order.return_value = {"status": "canceled"}

        mock_dca_repo = AsyncMock()
        mock_dca_repo.get_all_orders_by_group_id.return_value = [partial_order]
        mock_dca_repo.update = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()

        with (
            patch("app.services.order_management.DCAOrderRepository", return_value=mock_dca_repo),
            patch("app.services.order_management.PositionGroupRepository")
        ):
            service = OrderService(
                session=mock_session,
                user=mock_user,
                exchange_connector=mock_connector
            )

            await service.cancel_open_orders_for_group(group_id)

            # Status should be CANCELLED
            assert partial_order.status == OrderStatus.CANCELLED.value

            # CRITICAL: filled_quantity must be preserved
            assert partial_order.filled_quantity == Decimal("0.05"), \
                "filled_quantity must be preserved when cancelling partial fill"
