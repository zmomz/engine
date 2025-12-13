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
from app.models.pyramid import Pyramid
from app.models.dca_order import DCAOrder, OrderStatus
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

        if not user or not user.telegram_config:
            return

        config = TelegramConfig(**user.telegram_config)

        if not config.enabled or not config.send_entry_signals:
            return

        # Get all pyramids for this position group
        result = await session.execute(
            select(Pyramid).where(Pyramid.group_id == position_group.id).order_by(Pyramid.pyramid_index)
        )
        all_pyramids = result.scalars().all()

        # Build entry prices and weights lists
        entry_prices: List[Optional[Decimal]] = []
        weights: List[int] = []

        for pyr in all_pyramids:
            if pyr.status == "filled":
                # Get filled DCA orders for this pyramid
                result = await session.execute(
                    select(DCAOrder)
                    .where(DCAOrder.pyramid_id == pyr.id)
                    .where(DCAOrder.status == OrderStatus.FILLED.value)
                )
                filled_orders = result.scalars().all()

                if filled_orders:
                    # Calculate average entry price for this pyramid
                    total_qty = sum(o.filled_quantity for o in filled_orders)
                    total_value = sum(o.filled_quantity * o.avg_fill_price for o in filled_orders)
                    avg_entry = total_value / total_qty if total_qty > 0 else Decimal("0")
                    entry_prices.append(avg_entry)
                else:
                    entry_prices.append(None)
            else:
                entry_prices.append(None)

            # Calculate weight (20%, 40%, 60%, 80%, 100%)
            weight = (pyr.pyramid_index + 1) * 20
            weights.append(weight)

        # Create broadcaster and send signal
        broadcaster = TelegramBroadcaster(config)
        await broadcaster.send_entry_signal(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights
        )

        logger.info(f"Sent entry signal for {position_group.symbol} pyramid {pyramid.pyramid_index}")

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
