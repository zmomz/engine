"""
Position exit and closing logic.
Handles closing positions, TP execution, and recording close actions.
"""
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.risk_action import RiskAction, RiskActionType
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.order_management import OrderService
logger = logging.getLogger(__name__)


def extract_fee_from_order_result(order_result: Dict[str, Any], fill_price: Decimal) -> Decimal:
    """
    Extract fee from exchange order result and convert to USD.

    Handles multiple formats:
    - CCXT: {'fee': {'cost': 0.001, 'currency': 'USDT'}}
    - Bybit raw: {'info': {'cumFeeDetail': {'BTC': '0.000009'}}}
    - Mock: {'fee': 0.001}

    Args:
        order_result: The exchange order response
        fill_price: The fill price for converting base currency fees to USD

    Returns:
        Fee amount in USD
    """
    quote_currencies = {"USDT", "BUSD", "USDC", "USD", "TUSD", "DAI"}

    # Try Bybit's cumFeeDetail first (most accurate)
    info = order_result.get("info", {})
    cum_fee_detail = info.get("cumFeeDetail", {})
    if cum_fee_detail and isinstance(cum_fee_detail, dict):
        for currency, amount in cum_fee_detail.items():
            if amount and Decimal(str(amount)) > 0:
                fee_amount = Decimal(str(amount))
                if currency.upper() in quote_currencies:
                    return fee_amount
                else:
                    # Convert base currency fee to USD
                    return fee_amount * fill_price if fill_price > 0 else fee_amount

    # Try CCXT unified format
    raw_fee = order_result.get("fee")
    if isinstance(raw_fee, dict):
        fee_cost = Decimal(str(raw_fee.get("cost", 0) or 0))
        fee_currency = (raw_fee.get("currency") or "").upper()
        if fee_cost > 0:
            if fee_currency in quote_currencies:
                return fee_cost
            else:
                # Convert base currency fee to USD
                return fee_cost * fill_price if fill_price > 0 else fee_cost
    elif raw_fee is not None:
        # Direct number (mock exchange)
        return Decimal(str(raw_fee))

    return Decimal("0")


def _get_exchange_connector_for_user(user: User, exchange_name: str) -> ExchangeInterface:
    """Get exchange connector for a user."""
    encrypted_data = user.encrypted_api_keys
    exchange_key = exchange_name.lower()

    if isinstance(encrypted_data, dict):
        if exchange_key in encrypted_data:
            exchange_config = encrypted_data[exchange_key]
        elif "encrypted_data" in encrypted_data and len(encrypted_data) == 1:
            exchange_config = encrypted_data
        else:
            raise ValueError(f"No API keys found for exchange {exchange_name} (normalized: {exchange_key}). Available: {list(encrypted_data.keys()) if encrypted_data else 'None'}")
    elif isinstance(encrypted_data, str):
        exchange_config = {"encrypted_data": encrypted_data}
    else:
        raise ValueError("Invalid format for encrypted_api_keys. Expected dict or str.")

    return get_exchange_connector(exchange_name, exchange_config)


async def save_close_action(
    session: AsyncSession,
    position_group: PositionGroup,
    exit_price: Decimal,
    exit_reason: str,
    realized_pnl: Decimal,
    quantity_closed: Decimal
):
    """
    Saves a close action to the risk_actions history table.

    Args:
        session: Database session
        position_group: The position group being closed
        exit_price: The exit price
        exit_reason: Reason for exit ("manual", "engine", "tp_hit", "risk_offset")
        realized_pnl: Realized PnL in USD
        quantity_closed: Quantity that was closed
    """
    try:
        # Map exit_reason to RiskActionType
        action_type_map = {
            "manual": RiskActionType.MANUAL_CLOSE,
            "engine": RiskActionType.ENGINE_CLOSE,
            "tp_hit": RiskActionType.TP_HIT,
            "risk_offset": RiskActionType.OFFSET_LOSS,
        }
        action_type = action_type_map.get(exit_reason, RiskActionType.ENGINE_CLOSE)

        # Calculate PnL percentage
        entry_price = position_group.weighted_avg_entry
        if entry_price and entry_price > 0:
            if position_group.side == "long":
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        else:
            pnl_percent = Decimal("0")

        # Calculate duration in seconds
        duration_seconds = None
        if position_group.created_at:
            close_time = position_group.closed_at or datetime.utcnow()
            duration = close_time - position_group.created_at
            duration_seconds = Decimal(str(duration.total_seconds()))

        # Create risk action record
        risk_action = RiskAction(
            group_id=position_group.id,
            action_type=action_type,
            exit_price=exit_price,
            entry_price=entry_price,
            pnl_percent=pnl_percent,
            realized_pnl_usd=realized_pnl,
            quantity_closed=quantity_closed,
            duration_seconds=duration_seconds,
            notes=f"Position closed via {exit_reason}. Symbol: {position_group.symbol}, Side: {position_group.side}"
        )

        risk_action_repo = RiskActionRepository(session)
        await risk_action_repo.create(risk_action)
        await session.flush()

        logger.info(f"Saved {action_type.value} action for PositionGroup {position_group.id}")

    except Exception as e:
        logger.error(f"Error saving close action for PositionGroup {position_group.id}: {e}")
        # Don't raise - history saving should not break the close flow


async def execute_handle_exit_signal(
    position_group_id: uuid.UUID,
    session: AsyncSession,
    user: User,
    position_group_repository_class: type[PositionGroupRepository],
    order_service_class: type[OrderService],
    max_slippage_percent: float = 1.0,
    slippage_action: str = "warn",
    exit_reason: str = "engine",
    update_position_stats_func: Optional[Callable] = None
):
    """
    Core logic for handling an exit signal within a provided session.

    Args:
        position_group_id: ID of the position group to close
        session: Database session
        user: The user
        position_group_repository_class: Repository class for position groups
        order_service_class: Service class for order management
        max_slippage_percent: Maximum acceptable slippage (default 1%)
        slippage_action: "warn" to log only, "reject" to raise error
        exit_reason: Reason for exit ("manual", "engine", "tp_hit", "risk_offset")
        update_position_stats_func: Optional function to recalculate position stats after order sync
    """
    # Re-fetch position group with orders attached in this session
    position_group_repo = position_group_repository_class(session)
    position_group = await position_group_repo.get_with_orders(position_group_id)

    if not position_group:
        logger.error(f"PositionGroup {position_group_id} not found for exit signal.")
        return

    # Check if already closed or closing
    if position_group.status == PositionGroupStatus.CLOSED:
        logger.warning(f"PositionGroup {position_group_id} is already closed. Skipping exit signal.")
        return

    # Transition to CLOSING status first
    if position_group.status != PositionGroupStatus.CLOSING:
        position_group.status = PositionGroupStatus.CLOSING
        await position_group_repo.update(position_group)
        await session.flush()
        logger.info(f"PositionGroup {position_group_id} status changed to CLOSING")

    exchange_connector = _get_exchange_connector_for_user(user, position_group.exchange)
    try:
        order_service = order_service_class(session=session, user=user, exchange_connector=exchange_connector)

        # 1. Sync order statuses with exchange BEFORE cancelling
        # This ensures we have accurate filled quantities before closing
        await order_service.sync_orders_for_group(position_group.id)
        logger.info(f"Synced order statuses with exchange for PositionGroup {position_group.id}")

        # 1b. Update position stats after syncing orders (ensures entry fees are calculated)
        # This is critical for accurate PnL calculation, especially for Bybit where fees are in base currency
        if update_position_stats_func:
            await update_position_stats_func(position_group.id, session=session)
            logger.info(f"Updated position stats after order sync for PositionGroup {position_group.id}")
            # Re-fetch position group with updated stats
            position_group = await position_group_repo.get_with_orders(position_group_id)

        # 2. Cancel open orders
        await order_service.cancel_open_orders_for_group(position_group.id)
        logger.info(f"Cancelled open orders for PositionGroup {position_group.id}")

        # 3. Wait briefly to let order_fill_monitor finish any concurrent updates
        # This avoids deadlocks and ensures we get fresh data
        import asyncio
        await asyncio.sleep(0.5)

        # 4. Re-fetch position group with fresh data
        session.expire_all()  # Clear any cached data (sync method)
        position_group = await position_group_repo.get_with_orders(position_group_id)

        # 5. Calculate total filled quantity from fresh DB query
        from sqlalchemy import select
        from app.models.dca_order import DCAOrder

        result = await session.execute(
            select(DCAOrder.side, DCAOrder.filled_quantity, DCAOrder.status)
            .where(DCAOrder.group_id == position_group_id)
        )
        all_orders = result.fetchall()

        total_filled_quantity = Decimal("0")
        group_side = position_group.side.lower()
        filled_count = 0
        for row in all_orders:
            if row.status == "filled":
                filled_count += 1
                order_side = row.side.lower()
                qty = row.filled_quantity or Decimal("0")
                is_entry = (group_side == "long" and order_side == "buy") or \
                           (group_side == "short" and order_side == "sell")
                if is_entry:
                    total_filled_quantity += qty
                else:
                    total_filled_quantity -= qty

        logger.info(f"Calculated total_filled_quantity={total_filled_quantity} ({filled_count} filled orders) for PositionGroup {position_group.id}")

        if total_filled_quantity > 0:
            # 3. Close the position with slippage protection
            current_price = Decimal(str(await exchange_connector.get_current_price(position_group.symbol)))

            # Fetch dynamic fee rate from exchange (fallback to 0.1% if unavailable)
            try:
                fee_rate = Decimal(str(await exchange_connector.get_trading_fee_rate(position_group.symbol)))
            except Exception:
                fee_rate = Decimal("0.001")  # 0.1% fallback

            try:
                # Place market order and get result with fee info
                order_result = await order_service.close_position_market(
                    position_group=position_group,
                    quantity_to_close=total_filled_quantity,
                    expected_price=current_price,
                    max_slippage_percent=max_slippage_percent,
                    slippage_action=slippage_action
                )
                logger.info(f"Placed market order to close {total_filled_quantity} for PositionGroup {position_group.id}")

                # Extract actual fill price from order result
                actual_fill_price = current_price
                if order_result:
                    avg_price_raw = order_result.get("average") or order_result.get("avg_price") or order_result.get("price")
                    if avg_price_raw:
                        actual_fill_price = Decimal(str(avg_price_raw))

                # Extract actual exit fee from order result (converted to USD)
                actual_exit_fee = extract_fee_from_order_result(order_result or {}, actual_fill_price)
                if actual_exit_fee > 0:
                    logger.info(f"Actual exit fee extracted: {actual_exit_fee} USD")
                else:
                    # Fallback to estimated fee if actual not available
                    actual_exit_fee = total_filled_quantity * actual_fill_price * fee_rate
                    logger.info(f"Exit fee estimated (no actual fee in response): {actual_exit_fee} USD")

                # If successful, update position status and PnL
                position_group.status = PositionGroupStatus.CLOSED

                exit_value = total_filled_quantity * actual_fill_price
                cost_basis = position_group.total_invested_usd  # Already includes entry fees

                if position_group.side == "long":
                    realized_pnl = exit_value - cost_basis - actual_exit_fee
                else:
                    realized_pnl = cost_basis - exit_value - actual_exit_fee

                position_group.realized_pnl_usd = realized_pnl
                position_group.unrealized_pnl_usd = Decimal("0")
                position_group.total_exit_fees_usd = (position_group.total_exit_fees_usd or Decimal("0")) + actual_exit_fee
                position_group.closed_at = datetime.utcnow()

                await position_group_repo.update(position_group)
                logger.info(f"PositionGroup {position_group.id} closed. Exit fee: {actual_exit_fee} USD, Realized PnL: {realized_pnl}")

                # Save risk action to history
                await save_close_action(
                    session=session,
                    position_group=position_group,
                    exit_price=actual_fill_price,
                    exit_reason=exit_reason,
                    realized_pnl=realized_pnl,
                    quantity_closed=total_filled_quantity
                )

                # Note: Telegram broadcast skipped here - handled by status change notification instead
                # Background tasks with shared session cause "session is in prepared state" errors

            except Exception as e:
                logger.error(f"DEBUG: Caught exception in handle_exit_signal: {type(e)} - {e}")
                error_msg = str(e).lower()
                if "insufficient" in error_msg:
                    logger.warning(f"Insufficient funds to close {total_filled_quantity} for Group {position_group.id}. Attempting to close max available balance.")

                    balance_data = None  # Initialize to avoid reference before assignment
                    try:
                        # Heuristic to find base currency
                        symbol = position_group.symbol
                        base_currency = symbol
                        for quote in ["USDT", "USDC", "BUSD", "USD", "EUR", "DAI"]:
                            if symbol.endswith(quote):
                                base_currency = symbol[:-len(quote)]
                                break

                        # Fetch balance
                        balance_data = await exchange_connector.fetch_free_balance()
                        balance_value = balance_data.get(base_currency)
                        # Handle None values - Bybit may return None for zero balances
                        available_balance = Decimal(str(balance_value)) if balance_value is not None else Decimal("0")

                        if available_balance > 0:
                            logger.info(f"Retrying close with available balance: {available_balance} {base_currency}")
                            retry_order_result = await order_service.close_position_market(
                                position_group=position_group,
                                quantity_to_close=available_balance
                            )

                            # Extract actual fill price from retry order result
                            retry_fill_price = Decimal(str(await exchange_connector.get_current_price(position_group.symbol)))
                            if retry_order_result:
                                avg_price_raw = retry_order_result.get("average") or retry_order_result.get("avg_price") or retry_order_result.get("price")
                                if avg_price_raw:
                                    retry_fill_price = Decimal(str(avg_price_raw))

                            # Extract actual exit fee from retry order result
                            retry_exit_fee = extract_fee_from_order_result(retry_order_result or {}, retry_fill_price)
                            if retry_exit_fee == 0:
                                # Fallback to estimated fee
                                retry_exit_fee = available_balance * retry_fill_price * fee_rate

                            # If retry is successful, update status and commit
                            position_group.status = PositionGroupStatus.CLOSED
                            exit_value = available_balance * retry_fill_price
                            cost_basis = position_group.total_invested_usd  # Already includes entry fees

                            if position_group.side == "long":
                                realized_pnl = exit_value - cost_basis - retry_exit_fee
                            else:
                                realized_pnl = cost_basis - exit_value - retry_exit_fee

                            position_group.realized_pnl_usd = realized_pnl
                            position_group.unrealized_pnl_usd = Decimal("0")
                            position_group.total_exit_fees_usd = (position_group.total_exit_fees_usd or Decimal("0")) + retry_exit_fee
                            position_group.closed_at = datetime.utcnow()
                            await position_group_repo.update(position_group)
                            logger.info(f"PositionGroup {position_group.id} closed after retry. Exit fee: {retry_exit_fee} USD, Realized PnL: {realized_pnl}")

                            # Save risk action to history
                            await save_close_action(
                                session=session,
                                position_group=position_group,
                                exit_price=retry_fill_price,
                                exit_reason=exit_reason,
                                realized_pnl=realized_pnl,
                                quantity_closed=available_balance
                            )

                            # Note: Telegram broadcast skipped here - handled by status change notification instead

                        else:
                            logger.error(f"No balance found for {base_currency}. Cannot retry close.")
                            raise e
                    except Exception as retry_e:
                        logger.info(f"DEBUG: Free Balance Data: {balance_data}")
                        logger.error(f"Retry close failed: {retry_e}")
                        raise e
                else:
                    raise e
        else:
            logger.info(f"No filled quantity to close for PositionGroup {position_group.id}. Closing group.")
            position_group.status = PositionGroupStatus.CLOSED
            position_group.closed_at = datetime.utcnow()
            await position_group_repo.update(position_group)
    finally:
        await exchange_connector.close()
