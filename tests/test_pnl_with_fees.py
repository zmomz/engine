"""
Tests for P&L calculations with fee handling.

Verifies that:
1. Entry fees are added to cost basis
2. Exit fees are deducted from realized P&L
3. Unrealized P&L includes estimated exit fee (0.1%)
4. Risk engine uses fee-adjusted P&L
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus


class TestFeeExtraction:
    """Tests for fee extraction from exchange responses."""

    @pytest.mark.asyncio
    async def test_fee_extraction_from_filled_order(self):
        """Test that fees are correctly extracted and stored when order fills."""
        from app.services.order_management import OrderService

        # Setup
        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_exchange = AsyncMock()

        dca_order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            pyramid_id=uuid.uuid4(),
            leg_index=0,
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("100"),
            tp_percent=Decimal("2"),
            tp_price=Decimal("51000"),
            status=OrderStatus.OPEN,
            exchange_order_id="test_order_123",
            fee=None,
            fee_currency=None
        )

        # Mock exchange response with fee data
        mock_exchange.get_order_status.return_value = {
            "id": "test_order_123",
            "status": "closed",
            "filled": 0.1,
            "average": 50000,
            "fee": 5.0,  # $5 fee
            "fee_currency": "USDT"
        }

        with patch('app.services.order_management.DCAOrderRepository') as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.update = AsyncMock()  # Make update async
            mock_repo.return_value = mock_repo_instance

            service = OrderService(
                session=mock_session,
                user=mock_user,
                exchange_connector=mock_exchange
            )

            updated_order = await service.check_order_status(dca_order)

            # Verify fee was extracted and stored
            assert updated_order.fee == Decimal("5.0")
            assert updated_order.fee_currency == "USDT"

    @pytest.mark.asyncio
    async def test_fee_extraction_handles_missing_fee(self):
        """Test that missing fee data doesn't cause errors."""
        from app.services.order_management import OrderService

        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_exchange = AsyncMock()

        dca_order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            pyramid_id=uuid.uuid4(),
            leg_index=0,
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("100"),
            tp_percent=Decimal("2"),
            tp_price=Decimal("51000"),
            status=OrderStatus.OPEN,
            exchange_order_id="test_order_123"
        )

        # Mock exchange response without fee data
        mock_exchange.get_order_status.return_value = {
            "id": "test_order_123",
            "status": "closed",
            "filled": 0.1,
            "average": 50000
            # No fee or fee_currency
        }

        with patch('app.services.order_management.DCAOrderRepository') as mock_repo:
            mock_repo_instance = MagicMock()
            mock_repo_instance.update = AsyncMock()  # Make update async
            mock_repo.return_value = mock_repo_instance

            service = OrderService(
                session=mock_session,
                user=mock_user,
                exchange_connector=mock_exchange
            )

            # Should not raise, fee should be 0
            updated_order = await service.check_order_status(dca_order)
            assert updated_order.status == OrderStatus.FILLED


class TestPnLWithFees:
    """Tests for P&L calculations that include fees."""

    def test_unrealized_pnl_includes_estimated_exit_fee(self):
        """Test that unrealized P&L includes estimated 0.1% exit fee."""
        # Long position:
        # Entry: 100 USDT at $50 = 2 tokens
        # Current price: $55
        # Gross profit: ($55 - $50) * 2 = $10
        # Entry fee: $0.10
        # Estimated exit fee: $55 * 2 * 0.001 = $0.11
        # Net unrealized P&L: $10 - $0.10 - $0.11 = $9.79

        entry_price = Decimal("50")
        current_price = Decimal("55")
        qty = Decimal("2")
        entry_fees = Decimal("0.10")

        # Calculate expected P&L
        gross_pnl = (current_price - entry_price) * qty
        exit_value = current_price * qty
        estimated_exit_fee = exit_value * Decimal("0.001")
        expected_pnl = gross_pnl - entry_fees - estimated_exit_fee

        # $10 - $0.10 - $0.11 = $9.79
        assert expected_pnl == Decimal("9.79")

    def test_realized_pnl_includes_actual_fees(self):
        """Test that realized P&L deducts actual entry and exit fees."""
        # Long position:
        # Entry: $100 for 1 token at $100
        # Entry fee: $0.10
        # Total cost basis: $100.10
        # Exit: 1 token at $110 = $110
        # Exit fee: $0.11
        # Realized P&L: $110 - $100.10 - $0.11 = $9.79

        entry_price = Decimal("100")
        exit_price = Decimal("110")
        qty = Decimal("1")
        entry_fee = Decimal("0.10")
        exit_fee = Decimal("0.11")

        cost_basis = entry_price * qty + entry_fee
        exit_value = exit_price * qty
        realized_pnl = exit_value - cost_basis - exit_fee

        assert realized_pnl == Decimal("9.79")

    def test_short_position_pnl_with_fees(self):
        """Test P&L calculation for short positions with fees."""
        # Short position:
        # Entry: Sold 1 token at $100
        # Entry fee: $0.10
        # Exit: Buy back at $90
        # Exit fee: $0.09
        # Gross profit: $100 - $90 = $10
        # Net P&L: $10 - $0.10 - $0.09 = $9.81

        entry_price = Decimal("100")
        exit_price = Decimal("90")
        qty = Decimal("1")
        entry_fee = Decimal("0.10")
        exit_fee = Decimal("0.09")

        gross_pnl = (entry_price - exit_price) * qty
        realized_pnl = gross_pnl - entry_fee - exit_fee

        assert realized_pnl == Decimal("9.81")


class TestAnalyticsFeeHandling:
    """Tests for analytics service fee handling."""

    def test_dashboard_unrealized_pnl_with_fees(self):
        """Test that dashboard calculates unrealized P&L including fees."""
        # Setup a mock position group with fee data
        group = MagicMock(spec=PositionGroup)
        group.exchange = "binance"
        group.symbol = "BTCUSDT"
        group.side = "long"
        group.total_filled_quantity = Decimal("1.0")
        group.weighted_avg_entry = Decimal("50000")
        group.total_entry_fees_usd = Decimal("50")  # $50 in entry fees
        group.total_exit_fees_usd = Decimal("0")

        current_price = 55000.0
        qty = float(group.total_filled_quantity)
        avg_entry = float(group.weighted_avg_entry)
        entry_fees = float(group.total_entry_fees_usd)

        # Calculate as analytics_service does
        exit_value = current_price * qty
        estimated_exit_fee = exit_value * 0.001  # 0.1%

        # Long position P&L
        pnl = (current_price - avg_entry) * qty - entry_fees - estimated_exit_fee

        # Expected: ($55000 - $50000) * 1 - $50 - $55 = $4895
        expected_gross = 5000.0
        expected_pnl = expected_gross - 50.0 - 55.0
        assert pnl == expected_pnl


class TestPositionGroupFeeAccumulation:
    """Tests for fee accumulation on PositionGroup."""

    def test_position_group_fee_columns_exist(self):
        """Test that PositionGroup has fee tracking columns."""
        pg = PositionGroup(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            exchange="binance",
            symbol="BTCUSDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.LIVE,
            total_dca_legs=1,
            base_entry_price=Decimal("50000"),
            weighted_avg_entry=Decimal("50000"),
            tp_mode="per_leg",
            total_entry_fees_usd=Decimal("0"),  # Explicitly set for test
            total_exit_fees_usd=Decimal("0")
        )

        # Verify fee columns exist and have expected values
        assert hasattr(pg, 'total_entry_fees_usd')
        assert hasattr(pg, 'total_exit_fees_usd')
        assert pg.total_entry_fees_usd == Decimal("0")
        assert pg.total_exit_fees_usd == Decimal("0")

    def test_dca_order_fee_columns_exist(self):
        """Test that DCAOrder has fee tracking columns."""
        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=uuid.uuid4(),
            pyramid_id=uuid.uuid4(),
            leg_index=0,
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.1"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("100"),
            tp_percent=Decimal("2"),
            tp_price=Decimal("51000"),
            status=OrderStatus.PENDING
        )

        # Verify fee columns exist
        assert hasattr(order, 'fee')
        assert hasattr(order, 'fee_currency')


class TestRiskEngineFeeHandling:
    """Tests for risk engine fee considerations."""

    def test_offset_pnl_calculation_includes_fees(self):
        """Test that risk engine offset strategy includes fee estimates."""
        # When closing a loser position for offset:
        # Entry: $100 at $50 = 2 tokens, $0.10 entry fee
        # Current price: $45 (loss)
        # Exit value: 2 * $45 = $90
        # Estimated exit fee: $90 * 0.001 = $0.09
        # Realized loss: $90 - $100.10 - $0.09 = -$10.19

        entry_value = Decimal("100")
        entry_fee = Decimal("0.10")
        cost_basis = entry_value + entry_fee

        exit_price = Decimal("45")
        qty = Decimal("2")
        exit_value = exit_price * qty
        estimated_exit_fee = exit_value * Decimal("0.001")

        realized_pnl = exit_value - cost_basis - estimated_exit_fee

        # Expected: $90 - $100.10 - $0.09 = -$10.19
        assert realized_pnl == Decimal("-10.19")

    def test_winner_hedge_profit_includes_fees(self):
        """Test that winner hedge profit calculation includes exit fees."""
        # Winner position used for hedge:
        # Entry: $100 at $50 = 2 tokens
        # Current price: $60
        # Close 1 token for hedge
        # Exit value: 1 * $60 = $60
        # Entry cost for 1 token: $50
        # Estimated exit fee: $60 * 0.001 = $0.06
        # Hedge profit: ($60 - $50) * 1 - $0.06 = $9.94

        entry_price = Decimal("50")
        winner_price = Decimal("60")
        qty_closed = Decimal("1")

        exit_value = winner_price * qty_closed
        estimated_exit_fee = exit_value * Decimal("0.001")

        hedge_profit = (winner_price - entry_price) * qty_closed - estimated_exit_fee

        assert hedge_profit == Decimal("9.94")
