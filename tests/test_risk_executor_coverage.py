"""
Comprehensive tests for services/risk/risk_executor.py to achieve 100% coverage.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid

from app.services.risk.risk_executor import (
    round_to_step_size,
    calculate_partial_close_quantities
)
from app.models.position_group import PositionGroup
from app.models.user import User


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.encrypted_api_keys = {
        "binance": {"encrypted_data": "test_key", "testnet": True},
        "bybit": {"encrypted_data": "test_key2", "testnet": False}
    }
    return user


@pytest.fixture
def mock_winner():
    """Create a mock winning position."""
    winner = MagicMock(spec=PositionGroup)
    winner.id = uuid.uuid4()
    winner.symbol = "BTCUSDT"
    winner.exchange = "binance"
    winner.side = "long"
    winner.weighted_avg_entry = Decimal("50000")
    winner.total_filled_quantity = Decimal("0.1")
    winner.unrealized_pnl_usd = Decimal("500")
    return winner


# --- Tests for round_to_step_size ---

def test_round_to_step_size_exact():
    """Test rounding when value is exact multiple of step."""
    result = round_to_step_size(Decimal("0.100"), Decimal("0.001"))
    assert result == Decimal("0.100")


def test_round_to_step_size_round_down():
    """Test rounding down to step size."""
    result = round_to_step_size(Decimal("0.1234"), Decimal("0.01"))
    assert result == Decimal("0.12")


def test_round_to_step_size_round_up():
    """Test rounding up to step size."""
    result = round_to_step_size(Decimal("0.1256"), Decimal("0.01"))
    assert result == Decimal("0.13")


def test_round_to_step_size_large_step():
    """Test rounding with large step size."""
    result = round_to_step_size(Decimal("127.5"), Decimal("10"))
    assert result == Decimal("130")


def test_round_to_step_size_small_value():
    """Test rounding very small values."""
    result = round_to_step_size(Decimal("0.00045"), Decimal("0.0001"))
    # Rounds to nearest step: 0.00045 / 0.0001 = 4.5 -> rounds to 4 -> 4 * 0.0001 = 0.0004
    assert result == Decimal("0.0004")


# --- Tests for calculate_partial_close_quantities ---

@pytest.mark.asyncio
async def test_calculate_partial_close_basic(mock_user, mock_winner):
    """Test basic partial close calculation."""
    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("55000")  # 10% profit
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    required_usd = Decimal("250")

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], required_usd)

    assert len(plan) == 1
    position, qty = plan[0]
    assert position == mock_winner
    # Profit per unit = 55000 - 50000 = 5000
    # Qty = 250 / 5000 = 0.05
    assert qty == Decimal("0.050")


@pytest.mark.asyncio
async def test_calculate_partial_close_short_position(mock_user):
    """Test partial close for short position."""
    winner = MagicMock(spec=PositionGroup)
    winner.symbol = "ETHUSDT"
    winner.exchange = "binance"
    winner.side = "short"
    winner.weighted_avg_entry = Decimal("2000")
    winner.total_filled_quantity = Decimal("5.0")
    winner.unrealized_pnl_usd = Decimal("500")

    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("1800")  # Price dropped, profit for short
    mock_connector.get_precision_rules.return_value = {
        "ETHUSDT": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    required_usd = Decimal("200")

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [winner], required_usd)

    assert len(plan) == 1
    # Profit per unit for short = 2000 - 1800 = 200
    # Qty = 200 / 200 = 1.0
    assert plan[0][1] == Decimal("1.00")


@pytest.mark.asyncio
async def test_calculate_partial_close_zero_required(mock_user, mock_winner):
    """Test when required_usd is zero."""
    plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("0"))
    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_no_winners(mock_user):
    """Test with empty winners list."""
    plan = await calculate_partial_close_quantities(mock_user, [], Decimal("100"))
    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_profit_per_unit_zero(mock_user, mock_winner):
    """Test when profit per unit is zero (price equals entry)."""
    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("50000")  # Same as entry
    mock_connector.get_precision_rules.return_value = {}
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_profit_per_unit_negative(mock_user, mock_winner):
    """Test when profit per unit is negative (long position in loss)."""
    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("45000")  # Below entry
    mock_connector.get_precision_rules.return_value = {}
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_below_min_notional(mock_user, mock_winner):
    """Test when calculated quantity is below minimum notional."""
    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("55000")
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("1000")}  # High min
    }
    mock_connector.close = AsyncMock()

    required_usd = Decimal("10")  # Very small amount

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], required_usd)

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_skips_when_would_close_entire_position(mock_user, mock_winner):
    """Test that winner is skipped when calculation would close entire position.

    The risk executor protects winners by skipping them if the calculated
    quantity_to_close >= total_filled_quantity. This ensures we never
    fully close a winning position during offset.
    """
    mock_winner.total_filled_quantity = Decimal("0.01")  # Very small quantity

    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("55000")
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    required_usd = Decimal("1000")  # Would require more than available

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], required_usd)

    # Winner is skipped because closing it entirely is not allowed
    # profit_per_unit = 55000 - 50000 = 5000, qty = 1000/5000 = 0.2, but total_filled = 0.01
    assert len(plan) == 0, "Winner should be skipped when it would require closing entire position"


@pytest.mark.asyncio
async def test_calculate_partial_close_multiple_winners(mock_user):
    """Test with multiple winners when first winner can't cover required amount."""
    winner1 = MagicMock(spec=PositionGroup)
    winner1.symbol = "BTCUSDT"
    winner1.exchange = "binance"
    winner1.side = "long"
    winner1.weighted_avg_entry = Decimal("50000")
    winner1.total_filled_quantity = Decimal("0.1")
    winner1.unrealized_pnl_usd = Decimal("50")  # Small profit, won't cover required

    winner2 = MagicMock(spec=PositionGroup)
    winner2.symbol = "ETHUSDT"
    winner2.exchange = "binance"
    winner2.side = "long"
    winner2.weighted_avg_entry = Decimal("2000")
    winner2.total_filled_quantity = Decimal("2.0")
    winner2.unrealized_pnl_usd = Decimal("400")  # Larger profit

    mock_connector = AsyncMock()
    mock_connector.get_current_price.side_effect = [Decimal("52000"), Decimal("2200")]
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "ETHUSDT": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    required_usd = Decimal("100")  # Needs both winners to cover

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [winner1, winner2], required_usd)

    # At least 1 winner should be included (first winner has $50 profit, so needs second)
    assert len(plan) >= 1, f"Expected at least 1 winner, got {len(plan)}"


@pytest.mark.asyncio
async def test_calculate_partial_close_connector_init_error(mock_user, mock_winner):
    """Test handling connector initialization error."""
    with patch("app.services.risk.risk_executor.get_exchange_connector", side_effect=Exception("Init failed")):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_price_fetch_error(mock_user, mock_winner):
    """Test handling price fetch error."""
    mock_connector = AsyncMock()
    mock_connector.get_current_price.side_effect = Exception("Price API error")
    mock_connector.get_precision_rules.return_value = {}
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_precision_rules_error(mock_user, mock_winner):
    """Test handling precision rules fetch error."""
    mock_connector = AsyncMock()
    mock_connector.get_precision_rules.side_effect = Exception("Precision API error")
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_missing_exchange_keys(mock_winner):
    """Test when user doesn't have keys for the exchange."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.encrypted_api_keys = {"bybit": {"encrypted_data": "test"}}  # Only bybit, not binance

    mock_winner.exchange = "binance"

    plan = await calculate_partial_close_quantities(user, [mock_winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_legacy_string_format():
    """Test with legacy string format for encrypted_api_keys."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.encrypted_api_keys = "legacy_encrypted_string"

    winner = MagicMock(spec=PositionGroup)
    winner.symbol = "BTCUSDT"
    winner.exchange = "binance"
    winner.side = "long"
    winner.weighted_avg_entry = Decimal("50000")
    winner.total_filled_quantity = Decimal("0.1")
    winner.unrealized_pnl_usd = Decimal("500")

    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("55000")
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(user, [winner], Decimal("100"))

    assert len(plan) == 1


@pytest.mark.asyncio
async def test_calculate_partial_close_invalid_api_keys_format():
    """Test with invalid format for encrypted_api_keys."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.encrypted_api_keys = 12345  # Invalid format

    winner = MagicMock(spec=PositionGroup)
    winner.symbol = "BTCUSDT"
    winner.exchange = "binance"

    plan = await calculate_partial_close_quantities(user, [winner], Decimal("100"))

    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_multi_exchange(mock_user):
    """Test with positions from multiple exchanges when first can't cover all."""
    winner1 = MagicMock(spec=PositionGroup)
    winner1.symbol = "BTCUSDT"
    winner1.exchange = "binance"
    winner1.side = "long"
    winner1.weighted_avg_entry = Decimal("50000")
    winner1.total_filled_quantity = Decimal("0.1")
    winner1.unrealized_pnl_usd = Decimal("50")  # Small profit, won't cover required

    winner2 = MagicMock(spec=PositionGroup)
    winner2.symbol = "ETHUSDT"
    winner2.exchange = "bybit"
    winner2.side = "long"
    winner2.weighted_avg_entry = Decimal("2000")
    winner2.total_filled_quantity = Decimal("2.0")
    winner2.unrealized_pnl_usd = Decimal("400")

    mock_connector_binance = AsyncMock()
    mock_connector_binance.get_current_price.return_value = Decimal("52000")
    mock_connector_binance.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }
    mock_connector_binance.close = AsyncMock()

    mock_connector_bybit = AsyncMock()
    mock_connector_bybit.get_current_price.return_value = Decimal("2200")
    mock_connector_bybit.get_precision_rules.return_value = {
        "ETHUSDT": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")}
    }
    mock_connector_bybit.close = AsyncMock()

    def get_connector_side_effect(exchange_type, exchange_config):
        if exchange_type == "bybit":
            return mock_connector_bybit
        return mock_connector_binance

    with patch("app.services.risk.risk_executor.get_exchange_connector", side_effect=get_connector_side_effect):
        plan = await calculate_partial_close_quantities(mock_user, [winner1, winner2], Decimal("100"))

    # At least 1 winner should be included
    assert len(plan) >= 1, f"Expected at least 1 winner in plan, got {len(plan)}"
    # Both connectors should be closed
    mock_connector_binance.close.assert_called_once()
    mock_connector_bybit.close.assert_called_once()


@pytest.mark.asyncio
async def test_calculate_partial_close_reuses_connector(mock_user):
    """Test that connector is reused for same exchange."""
    winner1 = MagicMock(spec=PositionGroup)
    winner1.symbol = "BTCUSDT"
    winner1.exchange = "binance"
    winner1.side = "long"
    winner1.weighted_avg_entry = Decimal("50000")
    winner1.total_filled_quantity = Decimal("0.1")
    winner1.unrealized_pnl_usd = Decimal("200")

    winner2 = MagicMock(spec=PositionGroup)
    winner2.symbol = "ETHUSDT"
    winner2.exchange = "binance"  # Same exchange
    winner2.side = "long"
    winner2.weighted_avg_entry = Decimal("2000")
    winner2.total_filled_quantity = Decimal("2.0")
    winner2.unrealized_pnl_usd = Decimal("400")

    mock_connector = AsyncMock()
    mock_connector.get_current_price.side_effect = [Decimal("55000"), Decimal("2200")]
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")},
        "ETHUSDT": {"step_size": Decimal("0.01"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector) as mock_get:
        plan = await calculate_partial_close_quantities(mock_user, [winner1, winner2], Decimal("400"))

    # Connector should only be created once
    mock_get.assert_called_once()
    # But should be closed
    mock_connector.close.assert_called_once()


@pytest.mark.asyncio
async def test_calculate_partial_close_default_precision(mock_user, mock_winner):
    """Test using default precision when symbol not in precision rules."""
    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("55000")
    mock_connector.get_precision_rules.return_value = {}  # Empty rules
    mock_connector.close = AsyncMock()

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [mock_winner], Decimal("100"))

    assert len(plan) == 1
    # Should use default step_size of 0.001 and min_notional of 10


@pytest.mark.asyncio
async def test_calculate_partial_close_dict_without_encrypted_data():
    """Test when encrypted_api_keys dict doesn't have 'encrypted_data' key for unknown exchange."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.encrypted_api_keys = {"binance": {"api_key": "key", "api_secret": "secret"}}  # No 'encrypted_data'

    winner = MagicMock(spec=PositionGroup)
    winner.symbol = "BTCUSDT"
    winner.exchange = "kraken"  # Exchange not in keys

    plan = await calculate_partial_close_quantities(user, [winner], Decimal("100"))

    # Should skip because kraken not in keys and no fallback encrypted_data
    assert len(plan) == 0


@pytest.mark.asyncio
async def test_calculate_partial_close_satisfied_early(mock_user):
    """Test that loop stops when required amount is satisfied."""
    winner1 = MagicMock(spec=PositionGroup)
    winner1.symbol = "BTCUSDT"
    winner1.exchange = "binance"
    winner1.side = "long"
    winner1.weighted_avg_entry = Decimal("50000")
    winner1.total_filled_quantity = Decimal("0.1")
    winner1.unrealized_pnl_usd = Decimal("1000")  # More than enough

    winner2 = MagicMock(spec=PositionGroup)
    winner2.symbol = "ETHUSDT"
    winner2.exchange = "binance"
    winner2.side = "long"
    winner2.weighted_avg_entry = Decimal("2000")
    winner2.total_filled_quantity = Decimal("2.0")
    winner2.unrealized_pnl_usd = Decimal("500")

    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("55000")
    mock_connector.get_precision_rules.return_value = {
        "BTCUSDT": {"step_size": Decimal("0.001"), "min_notional": Decimal("10")}
    }
    mock_connector.close = AsyncMock()

    required_usd = Decimal("100")  # Small amount, first winner has enough

    with patch("app.services.risk.risk_executor.get_exchange_connector", return_value=mock_connector):
        plan = await calculate_partial_close_quantities(mock_user, [winner1, winner2], required_usd)

    # Only first winner should be used
    assert len(plan) == 1
    assert plan[0][0] == winner1

    # CRITICAL: Verify the planned close quantity
    position, close_qty = plan[0]
    assert close_qty > Decimal("0"), "Close quantity must be positive"
    assert close_qty <= position.total_filled_quantity, \
        "Close quantity must not exceed position quantity"

    # Verify connector was properly closed
    mock_connector.close.assert_called_once()
