"""
Offset execution logic for the Risk Engine.
Handles calculating partial close quantities and precision handling.
"""
import logging
from decimal import Decimal
from typing import List, Tuple

from app.models.position_group import PositionGroup
from app.models.user import User
from app.services.exchange_abstraction.factory import get_exchange_connector

logger = logging.getLogger(__name__)


def round_to_step_size(value: Decimal, step_size: Decimal) -> Decimal:
    """Round a value to the nearest step size."""
    return (value / step_size).quantize(Decimal('1')) * step_size


async def calculate_partial_close_quantities(
    user: User,
    winners: List[PositionGroup],
    required_usd: Decimal
) -> List[Tuple[PositionGroup, Decimal]]:
    """
    Calculate how much to close from each winner to realize required_usd.

    Returns: List of (PositionGroup, quantity_to_close)
    """
    close_plan = []
    remaining_needed = required_usd

    encrypted_data = user.encrypted_api_keys

    # Cache connectors to avoid re-initializing for same exchange
    connectors = {}
    precision_rules_cache = {}

    for winner in winners:
        if remaining_needed <= 0:
            break

        exchange_name = winner.exchange.lower()

        # Get Connector
        if exchange_name not in connectors:
            exchange_config = {}
            if isinstance(encrypted_data, dict):
                if exchange_name in encrypted_data:
                    exchange_config = encrypted_data[exchange_name]
                elif "encrypted_data" not in encrypted_data:
                    logger.error(f"Risk Engine: Keys for {exchange_name} not found for user {user.id}. Skipping winner {winner.symbol}.")
                    continue
                else:
                    exchange_config = {"encrypted_data": encrypted_data}
            elif isinstance(encrypted_data, str):
                exchange_config = {"encrypted_data": encrypted_data}
            else:
                logger.error(f"Risk Engine: Invalid format for encrypted_api_keys. Skipping.")
                continue

            try:
                connectors[exchange_name] = get_exchange_connector(exchange_type=exchange_name, exchange_config=exchange_config)
            except Exception as e:
                logger.error(f"Risk Engine: Failed to init connector for {exchange_name}: {e}")
                continue

        exchange_connector = connectors[exchange_name]

        # Get Precision Rules
        if exchange_name not in precision_rules_cache:
            try:
                precision_rules_cache[exchange_name] = await exchange_connector.get_precision_rules()
            except Exception as e:
                 logger.error(f"Risk Engine: Failed to fetch precision rules for {exchange_name}: {e}")
                 continue

        precision_rules = precision_rules_cache[exchange_name]

        # Calculate how much profit this winner can contribute
        available_profit = Decimal(str(winner.unrealized_pnl_usd))

        # Determine how much of this winner to close
        profit_to_take = min(available_profit, remaining_needed)

        # Calculate quantity to close to realize this profit
        try:
            current_price = await exchange_connector.get_current_price(winner.symbol)
            current_price = Decimal(str(current_price))
        except Exception as e:
            logger.error(f"Risk Engine: Failed to get price for {winner.symbol}: {e}")
            continue

        profit_per_unit = current_price - Decimal(str(winner.weighted_avg_entry))
        if winner.side == "short":
            profit_per_unit = Decimal(str(winner.weighted_avg_entry)) - current_price

        if profit_per_unit <= 0:
            logger.warning(f"Cannot calculate quantity for {winner.symbol}: profit_per_unit is zero or negative ({profit_per_unit}).")
            continue

        quantity_to_close = profit_to_take / profit_per_unit

        # Round to step size
        symbol_precision = precision_rules.get(winner.symbol, {})
        step_size = Decimal(str(symbol_precision.get("step_size", Decimal("0.001"))))
        quantity_to_close = round_to_step_size(quantity_to_close, step_size)

        # Check minimum notional
        notional_value = quantity_to_close * current_price
        min_notional = Decimal(str(symbol_precision.get("min_notional", Decimal("10"))))

        if notional_value < min_notional:
            logger.warning(
                f"Partial close for {winner.symbol} below min notional "
                f"({notional_value} < {min_notional}). Skipping."
            )
            continue

        # Cap at available quantity
        total_filled = Decimal(str(winner.total_filled_quantity))
        if quantity_to_close > total_filled:
            quantity_to_close = total_filled

        close_plan.append((winner, quantity_to_close))
        remaining_needed -= profit_to_take

    # Close connectors
    for conn in connectors.values():
        await conn.close()

    return close_plan
