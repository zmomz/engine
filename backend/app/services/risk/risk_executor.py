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
) -> Tuple[List[Tuple[PositionGroup, Decimal]], Decimal]:
    """
    Calculate how much to close from each winner to realize required_usd.

    Returns: Tuple of (close_plan, total_profit_realizable)
        - close_plan: List of (PositionGroup, quantity_to_close)
        - total_profit_realizable: Total profit that will be realized from the plan
    """
    total_profit_realizable = Decimal("0")
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

        # Calculate quantity to close to realize this profit
        try:
            current_price = await exchange_connector.get_current_price(winner.symbol)
            current_price = Decimal(str(current_price))
        except Exception as e:
            logger.error(f"Risk Engine: Failed to get price for {winner.symbol}: {e}")
            continue

        # For SPOT trading: All positions are "long"
        # Profit = current_price - entry_price
        profit_per_unit = current_price - Decimal(str(winner.weighted_avg_entry))

        if profit_per_unit <= 0:
            logger.warning(f"Cannot calculate quantity for {winner.symbol}: profit_per_unit is zero or negative ({profit_per_unit}).")
            continue

        # Get precision rules for this symbol
        symbol_precision = precision_rules.get(winner.symbol, {})
        step_size = Decimal(str(symbol_precision.get("step_size", Decimal("0.001"))))
        min_notional = Decimal(str(symbol_precision.get("min_notional", Decimal("10"))))
        total_filled = Decimal(str(winner.total_filled_quantity))

        # PROFIT-ONLY CONSTRAINT:
        # We can only sell units worth up to the unrealized profit amount
        # The CASH received from selling those units is the offset contribution
        # Rule: quantity × current_price <= unrealized_profit
        max_quantity_from_profit = available_profit / current_price

        # Round down to step size to stay within constraint
        max_quantity_from_profit = round_to_step_size(max_quantity_from_profit, step_size)

        # The cash we can contribute = max_quantity × current_price ≈ available_profit
        max_cash_contribution = max_quantity_from_profit * current_price

        logger.info(
            f"Risk Engine: Winner {winner.symbol} analysis - "
            f"unrealized=${available_profit:.2f}, price=${current_price}, "
            f"max_qty={max_quantity_from_profit}, max_contribution=${max_cash_contribution:.2f}"
        )

        # Determine how much cash to take from this winner (capped by what's available and what we need)
        cash_to_take = min(max_cash_contribution, remaining_needed)

        if cash_to_take <= 0:
            logger.warning(
                f"No contribution possible from {winner.symbol}. "
                f"max_contribution=${max_cash_contribution:.2f}. Skipping."
            )
            continue

        # Calculate quantity to close to get this cash
        # quantity = cash / current_price
        quantity_to_close = cash_to_take / current_price

        # Round to step size
        quantity_to_close = round_to_step_size(quantity_to_close, step_size)

        # Check minimum notional
        notional_value = quantity_to_close * current_price

        if notional_value < min_notional:
            logger.warning(
                f"Partial close for {winner.symbol} below min notional "
                f"({notional_value} < {min_notional}). Skipping."
            )
            continue

        # Safety check: ensure we're not closing more than position size
        if quantity_to_close > total_filled:
            logger.warning(
                f"Risk Engine: quantity_to_close ({quantity_to_close}) > total_filled ({total_filled}) "
                f"for {winner.symbol}. This shouldn't happen. Skipping."
            )
            continue

        logger.info(
            f"Risk Engine: Winner {winner.symbol} contributing ${cash_to_take:.2f} "
            f"(closing {quantity_to_close} of {total_filled}, {(quantity_to_close/total_filled*100):.1f}%)"
        )

        close_plan.append((winner, quantity_to_close))
        total_profit_realizable += cash_to_take
        remaining_needed -= cash_to_take

    # Close connectors
    for conn in connectors.values():
        await conn.close()

    logger.info(
        f"Risk Engine: Close plan complete - {len(close_plan)} winners, "
        f"total realizable profit=${total_profit_realizable:.2f}, "
        f"required=${required_usd:.2f}, shortfall=${max(Decimal('0'), remaining_needed):.2f}"
    )

    return close_plan, total_profit_realizable
