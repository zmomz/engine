"""
Helper functions for Telegram signal broadcasting
Integrates with position lifecycle events
"""
import logging
from typing import Optional, List
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.position_group import PositionGroup
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.dca_configuration import DCAConfiguration
from app.schemas.telegram_config import TelegramConfig
from app.services.telegram_broadcaster import TelegramBroadcaster

logger = logging.getLogger(__name__)


async def broadcast_entry_signal(
    position_group: PositionGroup,
    pyramid: Pyramid,
    session: AsyncSession
) -> None:
    """
    Broadcast entry signal when a new pyramid fills

    Args:
        position_group: The position group
        pyramid: The pyramid that was filled
        session: Database session
    """
    try:
        # Get user and telegram config
        result = await session.execute(
            select(User).where(User.id == position_group.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User {position_group.user_id} not found for Telegram broadcast")
            return

        if not user.telegram_config:
            logger.info(f"No Telegram config for user {user.username} - skipping broadcast")
            return

        config = TelegramConfig(**user.telegram_config)

        if not config.enabled:
            logger.info(f"Telegram disabled for user {user.username} - skipping broadcast")
            return

        if not config.send_entry_signals:
            logger.info(f"Entry signals disabled for user {user.username} - skipping broadcast")
            return

        # Get the DCA configuration to get the original percentage weights
        # Convert symbol format: BTCUSDT -> BTC/USDT
        pair_formatted = f"{position_group.symbol[:-4]}/{position_group.symbol[-4:]}" if position_group.symbol.endswith('USDT') else position_group.symbol

        result = await session.execute(
            select(DCAConfiguration).where(
                DCAConfiguration.user_id == position_group.user_id,
                DCAConfiguration.pair == pair_formatted,
                DCAConfiguration.timeframe == position_group.timeframe,
                DCAConfiguration.exchange == position_group.exchange
            )
        )
        dca_config = result.scalar_one_or_none()

        # Get all DCA orders for this pyramid to show entry levels
        result = await session.execute(
            select(DCAOrder)
            .where(DCAOrder.pyramid_id == pyramid.id)
            .order_by(DCAOrder.price.desc())  # Order by price descending (highest first)
        )
        dca_orders = result.scalars().all()

        # Build entry prices, weights, and TP data from DCA orders and config
        entry_prices: List[Optional[Decimal]] = []
        weights: List[int] = []
        tp_prices: List[Optional[Decimal]] = []
        tp_mode = None
        aggregate_tp = None

        # Get weights and TP data from DCA configuration levels
        if dca_config and dca_config.dca_levels:
            dca_levels = dca_config.dca_levels
            tp_mode = dca_config.tp_mode.value if hasattr(dca_config.tp_mode, 'value') else dca_config.tp_mode

            for i, order in enumerate(dca_orders):
                entry_prices.append(order.price)

                # Get the weight_percent from the configuration
                if i < len(dca_levels):
                    weight = int(float(dca_levels[i].get('weight_percent', 0)))

                    # Calculate TP for per_leg mode
                    if tp_mode == "per_leg":
                        tp_percent = dca_levels[i].get('tp_percent', 0)
                        if tp_percent and order.price:
                            # For long positions, TP is above entry
                            tp_price = order.price * (1 + Decimal(str(tp_percent)) / 100)
                            tp_prices.append(tp_price)
                        else:
                            tp_prices.append(None)
                else:
                    weight = 0
                    if tp_mode == "per_leg":
                        tp_prices.append(None)

                weights.append(weight)

            # Calculate aggregate TP if mode is aggregate
            if tp_mode == "aggregate" and dca_config.tp_settings:
                # Support both key names for backward compatibility
                aggregate_tp_percent = dca_config.tp_settings.get('tp_aggregate_percent') or dca_config.tp_settings.get('aggregate_tp_percent', 0)
                if aggregate_tp_percent:
                    # Calculate weighted average entry price using weight_percent
                    total_value = Decimal('0')
                    total_weight = Decimal('0')
                    for i, order in enumerate(dca_orders):
                        weight_pct = Decimal(str(dca_levels[i].get('weight_percent', 0))) if i < len(dca_levels) else Decimal('0')
                        total_value += order.price * weight_pct
                        total_weight += weight_pct

                    if total_weight > 0:
                        avg_entry = total_value / total_weight
                        aggregate_tp = avg_entry * (1 + Decimal(str(aggregate_tp_percent)) / 100)
        else:
            # Fallback: calculate from order quantities
            total_qty = sum(order.quantity for order in dca_orders)
            for order in dca_orders:
                entry_prices.append(order.price)
                if total_qty > 0:
                    weight = int((order.quantity / total_qty) * 100)
                else:
                    weight = int(100 / len(dca_orders))
                weights.append(weight)

        # Store the total number of DCA levels for the message
        max_pyramids = len(dca_orders)

        # Create broadcaster and send signal
        broadcaster = TelegramBroadcaster(config)

        logger.info(f"Broadcasting entry signal for {position_group.symbol} pyramid {pyramid.pyramid_index}")
        logger.debug(f"Entry prices: {entry_prices}, Weights: {weights}, TP mode: {tp_mode}, Aggregate TP: {aggregate_tp}")

        message_id = await broadcaster.send_entry_signal(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights,
            tp_prices=tp_prices if tp_mode == "per_leg" else None,
            tp_mode=tp_mode,
            aggregate_tp=aggregate_tp
        )

        if message_id:
            logger.info(f"Successfully sent entry signal for {position_group.symbol} pyramid {pyramid.pyramid_index} (message_id: {message_id})")
        else:
            logger.warning(f"Failed to send entry signal for {position_group.symbol} pyramid {pyramid.pyramid_index}")

    except Exception as e:
        logger.error(f"Error broadcasting entry signal: {e}")
        # Don't raise - Telegram errors shouldn't break trading logic


async def broadcast_exit_signal(
    position_group: PositionGroup,
    exit_price: Decimal,
    session: AsyncSession
) -> None:
    """
    Broadcast exit signal when a position is closed

    Args:
        position_group: The position group being closed
        exit_price: The exit price
        session: Database session
    """
    try:
        # Get user and telegram config
        result = await session.execute(
            select(User).where(User.id == position_group.user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.telegram_config:
            return

        config = TelegramConfig(**user.telegram_config)

        if not config.enabled or not config.send_exit_signals:
            return

        # Calculate PnL percentage
        entry_price = position_group.weighted_avg_entry
        if position_group.side == "long":
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100

        # Count pyramids used
        pyramids_used = position_group.pyramid_count

        # Create broadcaster and send signal
        broadcaster = TelegramBroadcaster(config)
        await broadcaster.send_exit_signal(
            position_group=position_group,
            exit_price=exit_price,
            pnl_percent=pnl_percent,
            pyramids_used=pyramids_used
        )

        logger.info(f"Sent exit signal for {position_group.symbol} at {exit_price}")

    except Exception as e:
        logger.error(f"Error broadcasting exit signal: {e}")
        # Don't raise - Telegram errors shouldn't break trading logic
