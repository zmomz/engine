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

        # Get all pyramids for this position group
        result = await session.execute(
            select(Pyramid).where(Pyramid.group_id == position_group.id).order_by(Pyramid.pyramid_index)
        )
        all_pyramids = result.scalars().all()

        # Build entry prices list - ALWAYS 5 elements
        # Create a mapping of pyramid_index -> entry_price
        pyramid_prices = {}

        for pyr in all_pyramids:
            # Show pyramid entry price for SUBMITTED or FILLED pyramids
            if pyr.status in [PyramidStatus.SUBMITTED, PyramidStatus.FILLED,
                             PyramidStatus.SUBMITTED.value, PyramidStatus.FILLED.value]:
                # Use the pyramid's base entry_price as the displayed price
                # This is the price from the signal when the pyramid was created
                pyramid_prices[pyr.pyramid_index] = pyr.entry_price

        # Build the list based on max_pyramids (dynamic)
        entry_prices: List[Optional[Decimal]] = []
        weights: List[int] = []

        max_pyramids = position_group.max_pyramids or 5  # Default to 5 if not set

        for i in range(max_pyramids):
            entry_prices.append(pyramid_prices.get(i, None))
            # Calculate weight dynamically based on total pyramids
            weight = int((i + 1) * 100 / max_pyramids)
            weights.append(weight)

        # Create broadcaster and send signal
        broadcaster = TelegramBroadcaster(config)

        logger.info(f"Broadcasting entry signal for {position_group.symbol} pyramid {pyramid.pyramid_index}")
        logger.debug(f"Entry prices: {entry_prices}, Weights: {weights}")

        message_id = await broadcaster.send_entry_signal(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights
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
