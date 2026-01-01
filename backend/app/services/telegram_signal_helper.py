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
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.dca_configuration import DCAConfiguration
from app.schemas.telegram_config import TelegramConfig
from app.services.telegram_broadcaster import TelegramBroadcaster

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_user_telegram_config(
    user_id,
    session: AsyncSession
) -> Optional[TelegramConfig]:
    """Get user's Telegram configuration if enabled"""
    try:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.telegram_config:
            return None

        config = TelegramConfig(**user.telegram_config)

        if not config.enabled:
            return None

        return config
    except Exception as e:
        logger.error(f"Error getting Telegram config: {e}")
        return None


async def _get_dca_config(
    position_group: PositionGroup,
    session: AsyncSession
) -> Optional[DCAConfiguration]:
    """Get DCA configuration for position"""
    try:
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
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting DCA config: {e}")
        return None


def _extract_weights_from_levels(dca_levels: list) -> List[int]:
    """Extract weight percentages from DCA levels"""
    weights = []
    for level in dca_levels:
        weight = int(float(level.get('weight_percent', 0)))
        weights.append(weight)
    return weights


def _calculate_tp_prices(
    entry_prices: List[Optional[Decimal]],
    dca_levels: list,
    tp_mode: str
) -> List[Optional[Decimal]]:
    """Calculate TP prices for per_leg mode"""
    tp_prices = []
    if tp_mode != "per_leg":
        return tp_prices

    for i, entry_price in enumerate(entry_prices):
        if i < len(dca_levels) and entry_price:
            tp_percent = dca_levels[i].get('tp_percent', 0)
            if tp_percent:
                tp_price = entry_price * (1 + Decimal(str(tp_percent)) / 100)
                tp_prices.append(tp_price)
            else:
                tp_prices.append(None)
        else:
            tp_prices.append(None)

    return tp_prices


def _calculate_aggregate_tp(
    avg_entry: Decimal,
    tp_percent: Decimal
) -> Optional[Decimal]:
    """Calculate aggregate TP price"""
    if avg_entry and tp_percent:
        return avg_entry * (1 + tp_percent / 100)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY SIGNAL
# ═══════════════════════════════════════════════════════════════════════════════

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
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_entry_signals:
            return

        dca_config = await _get_dca_config(position_group, session)

        # Get all DCA orders for this pyramid
        result = await session.execute(
            select(DCAOrder)
            .where(DCAOrder.pyramid_id == pyramid.id)
            .order_by(DCAOrder.price.desc())
        )
        dca_orders = result.scalars().all()

        # Build entry prices and weights
        entry_prices: List[Optional[Decimal]] = []
        weights: List[int] = []
        tp_prices: List[Optional[Decimal]] = []
        # Use position_group.tp_mode directly - it's always available (nullable=False)
        tp_mode = position_group.tp_mode
        aggregate_tp = None
        pyramid_tp_percent = None

        if dca_config and dca_config.dca_levels:
            dca_levels = dca_config.dca_levels

            for i, order in enumerate(dca_orders):
                entry_prices.append(order.price if order.status == OrderStatus.FILLED else None)

                if i < len(dca_levels):
                    weights.append(int(float(dca_levels[i].get('weight_percent', 0))))
                else:
                    weights.append(0)

            # Calculate TP prices based on mode
            tp_prices = _calculate_tp_prices(entry_prices, dca_levels, tp_mode)

            # Calculate aggregate/pyramid_aggregate TP
            if tp_mode in ["aggregate", "hybrid"] and dca_config.tp_settings:
                agg_percent = dca_config.tp_settings.get('tp_aggregate_percent') or dca_config.tp_settings.get('aggregate_tp_percent', 0)
                if agg_percent and position_group.weighted_avg_entry:
                    aggregate_tp = _calculate_aggregate_tp(
                        position_group.weighted_avg_entry,
                        Decimal(str(agg_percent))
                    )

            if tp_mode == "pyramid_aggregate" and dca_config.tp_settings:
                # Get pyramid-specific TP or fallback
                pyramid_tp_percents = dca_config.tp_settings.get('pyramid_tp_percents', {})
                pyramid_key = str(pyramid.pyramid_index)
                if pyramid_key in pyramid_tp_percents:
                    pyramid_tp_percent = Decimal(str(pyramid_tp_percents[pyramid_key]))
                else:
                    agg_percent = dca_config.tp_settings.get('tp_aggregate_percent', 0)
                    pyramid_tp_percent = Decimal(str(agg_percent)) if agg_percent else None

        else:
            # Fallback without DCA config
            for order in dca_orders:
                entry_prices.append(order.price if order.status == OrderStatus.FILLED else None)
                weights.append(int(100 / len(dca_orders)) if dca_orders else 0)

        # Calculate filled count
        filled_count = sum(1 for p in entry_prices if p is not None)
        total_count = len(entry_prices)

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        logger.info(f"Broadcasting entry signal for {position_group.symbol} pyramid {pyramid.pyramid_index}")

        await broadcaster.send_entry_signal(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights,
            filled_count=filled_count,
            total_count=total_count,
            tp_prices=tp_prices if tp_mode == "per_leg" else None,
            tp_mode=tp_mode,
            aggregate_tp=aggregate_tp,
            pyramid_tp_percent=pyramid_tp_percent,
            session=session
        )

    except Exception as e:
        logger.error(f"Error broadcasting entry signal: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# EXIT SIGNAL
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_exit_signal(
    position_group: PositionGroup,
    exit_price: Decimal,
    session: AsyncSession,
    exit_reason: str = "engine"
) -> None:
    """
    Broadcast exit signal when a position is closed

    Args:
        position_group: The position group being closed
        exit_price: The exit price
        session: Database session
        exit_reason: Reason for exit ("manual", "engine", "tp_hit", "risk_offset")
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_exit_signals:
            return

        # Calculate PnL percentage
        entry_price = position_group.weighted_avg_entry
        if entry_price and entry_price > 0:
            if position_group.side == "long":
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        else:
            pnl_percent = Decimal("0")

        pnl_usd = position_group.realized_pnl_usd

        # Calculate duration
        duration_hours = None
        if position_group.created_at:
            from datetime import datetime
            end_time = position_group.closed_at or datetime.utcnow()
            duration = end_time - position_group.created_at
            duration_hours = duration.total_seconds() / 3600

        # Use position_group.tp_mode directly - it's always available (nullable=False)
        tp_mode = position_group.tp_mode

        # Count filled legs
        filled_legs = position_group.filled_dca_legs or 0
        total_legs = position_group.total_dca_legs or 0

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        await broadcaster.send_exit_signal(
            position_group=position_group,
            exit_price=exit_price,
            pnl_percent=pnl_percent,
            pyramids_used=position_group.pyramid_count,
            exit_reason=exit_reason,
            pnl_usd=pnl_usd,
            duration_hours=duration_hours,
            filled_legs=filled_legs,
            total_legs=total_legs,
            tp_mode=tp_mode
        )

        logger.info(f"Sent exit signal for {position_group.symbol} at {exit_price} (reason: {exit_reason})")

    except Exception as e:
        logger.error(f"Error broadcasting exit signal: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# DCA FILL
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_dca_fill(
    position_group: PositionGroup,
    order: DCAOrder,
    pyramid: Pyramid,
    session: AsyncSession
) -> None:
    """
    Broadcast DCA leg fill notification

    Args:
        position_group: The position group
        order: The filled DCA order
        pyramid: The pyramid containing the order
        session: Database session
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_dca_fill_updates:
            return

        # Count filled orders in this pyramid
        result = await session.execute(
            select(DCAOrder).where(
                DCAOrder.pyramid_id == pyramid.id,
                DCAOrder.status == OrderStatus.FILLED
            )
        )
        filled_orders = result.scalars().all()
        filled_count = len(filled_orders)

        # Get total orders in pyramid
        result = await session.execute(
            select(DCAOrder).where(DCAOrder.pyramid_id == pyramid.id)
        )
        all_orders = result.scalars().all()
        total_count = len(all_orders)

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        await broadcaster.send_dca_fill(
            position_group=position_group,
            order=order,
            filled_count=filled_count,
            total_count=total_count,
            pyramid=pyramid,
            session=session
        )

        logger.info(f"Sent DCA fill notification for {position_group.symbol} leg {filled_count}/{total_count}")

    except Exception as e:
        logger.error(f"Error broadcasting DCA fill: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS CHANGE
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_status_change(
    position_group: PositionGroup,
    old_status: PositionGroupStatus,
    new_status: PositionGroupStatus,
    pyramid: Pyramid,
    session: AsyncSession
) -> None:
    """
    Broadcast status change notification

    Args:
        position_group: The position group
        old_status: Previous status
        new_status: New status
        pyramid: Current pyramid
        session: Database session
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_status_updates:
            return

        # Use position_group.tp_mode directly - it's always available (nullable=False)
        tp_mode = position_group.tp_mode

        # Get TP percent from position group if available
        tp_percent = position_group.tp_aggregate_percent

        # Get fill counts
        filled_count = position_group.filled_dca_legs or 0
        total_count = position_group.total_dca_legs or 0

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        old_status_str = old_status.value if hasattr(old_status, 'value') else str(old_status)
        new_status_str = new_status.value if hasattr(new_status, 'value') else str(new_status)

        await broadcaster.send_status_change(
            position_group=position_group,
            old_status=old_status_str,
            new_status=new_status_str,
            pyramid=pyramid,
            filled_count=filled_count,
            total_count=total_count,
            tp_mode=tp_mode,
            tp_percent=tp_percent
        )

        logger.info(f"Sent status change notification for {position_group.symbol}: {old_status_str} → {new_status_str}")

    except Exception as e:
        logger.error(f"Error broadcasting status change: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# TP HIT
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_tp_hit(
    position_group: PositionGroup,
    pyramid: Optional[Pyramid],
    tp_type: str,
    tp_price: Decimal,
    pnl_percent: Decimal,
    session: AsyncSession,
    pnl_usd: Optional[Decimal] = None,
    closed_quantity: Optional[Decimal] = None,
    remaining_pyramids: int = 0,
    leg_index: Optional[int] = None
) -> None:
    """
    Broadcast TP hit notification

    Args:
        position_group: The position group
        pyramid: The pyramid (if applicable)
        tp_type: Type of TP ("per_leg", "aggregate", "pyramid_aggregate")
        tp_price: The TP price hit
        pnl_percent: Profit percentage
        session: Database session
        pnl_usd: Profit in USD
        closed_quantity: Quantity closed
        remaining_pyramids: Number of pyramids still open
        leg_index: Index of leg (for per_leg TP)
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_tp_hit_updates:
            return

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        await broadcaster.send_tp_hit(
            position_group=position_group,
            pyramid=pyramid,
            tp_type=tp_type,
            tp_price=tp_price,
            pnl_percent=pnl_percent,
            pnl_usd=pnl_usd,
            closed_quantity=closed_quantity,
            remaining_pyramids=remaining_pyramids,
            leg_index=leg_index
        )

        logger.info(f"Sent TP hit notification for {position_group.symbol} ({tp_type})")

    except Exception as e:
        logger.error(f"Error broadcasting TP hit: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# RISK EVENT
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_risk_event(
    position_group: PositionGroup,
    event_type: str,
    session: AsyncSession,
    loss_percent: Optional[Decimal] = None,
    loss_usd: Optional[Decimal] = None,
    timer_minutes: Optional[int] = None,
    offset_position: Optional[str] = None,
    offset_profit: Optional[Decimal] = None,
    net_result: Optional[Decimal] = None
) -> None:
    """
    Broadcast risk event notification

    Args:
        position_group: The position group
        event_type: Type of event ("timer_started", "timer_expired", "timer_reset", "offset_executed")
        session: Database session
        loss_percent: Current loss percentage
        loss_usd: Current loss in USD
        timer_minutes: Timer duration in minutes
        offset_position: Symbol of position used for offset
        offset_profit: Profit from offset position
        net_result: Net result of offset operation
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_risk_alerts:
            return

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        await broadcaster.send_risk_event(
            position_group=position_group,
            event_type=event_type,
            loss_percent=loss_percent,
            loss_usd=loss_usd,
            timer_minutes=timer_minutes,
            offset_position=offset_position,
            offset_profit=offset_profit,
            net_result=net_result
        )

        logger.info(f"Sent risk event notification for {position_group.symbol} ({event_type})")

    except Exception as e:
        logger.error(f"Error broadcasting risk event: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_failure(
    position_group: PositionGroup,
    error_type: str,
    error_message: str,
    session: AsyncSession,
    pyramid: Optional[Pyramid] = None,
    order: Optional[DCAOrder] = None
) -> None:
    """
    Broadcast failure alert

    Args:
        position_group: The position group
        error_type: Type of error ("order_failed", "position_failed")
        error_message: Error message
        session: Database session
        pyramid: The pyramid (if applicable)
        order: The failed order (if applicable)
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_failure_alerts:
            return

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        await broadcaster.send_failure(
            position_group=position_group,
            error_type=error_type,
            error_message=error_message,
            pyramid=pyramid,
            order=order
        )

        logger.info(f"Sent failure alert for {position_group.symbol}: {error_message}")

    except Exception as e:
        logger.error(f"Error broadcasting failure: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PYRAMID ADDED
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_pyramid_added(
    position_group: PositionGroup,
    pyramid: Pyramid,
    session: AsyncSession
) -> None:
    """
    Broadcast new pyramid added notification

    Args:
        position_group: The position group
        pyramid: The new pyramid
        session: Database session
    """
    try:
        config = await _get_user_telegram_config(position_group.user_id, session)
        if not config or not config.send_pyramid_updates:
            return

        # Get DCA config
        dca_config = await _get_dca_config(position_group, session)

        # Get pyramid's DCA orders
        result = await session.execute(
            select(DCAOrder)
            .where(DCAOrder.pyramid_id == pyramid.id)
            .order_by(DCAOrder.price.desc())
        )
        dca_orders = result.scalars().all()

        # Build entry prices and weights
        entry_prices: List[Optional[Decimal]] = [order.price for order in dca_orders]
        weights: List[int] = []
        tp_percent = None

        if dca_config and dca_config.dca_levels:
            dca_levels = dca_config.dca_levels
            weights = _extract_weights_from_levels(dca_levels)

            # Get pyramid-specific TP
            if dca_config.tp_settings:
                pyramid_tp_percents = dca_config.tp_settings.get('pyramid_tp_percents', {})
                pyramid_key = str(pyramid.pyramid_index)
                if pyramid_key in pyramid_tp_percents:
                    tp_percent = Decimal(str(pyramid_tp_percents[pyramid_key]))
                else:
                    agg_percent = dca_config.tp_settings.get('tp_aggregate_percent', 0)
                    tp_percent = Decimal(str(agg_percent)) if agg_percent else None
        else:
            # Fallback
            weights = [int(100 / len(dca_orders))] * len(dca_orders) if dca_orders else []

        # Create broadcaster and send
        broadcaster = TelegramBroadcaster(config)

        await broadcaster.send_pyramid_added(
            position_group=position_group,
            pyramid=pyramid,
            entry_prices=entry_prices,
            weights=weights,
            tp_percent=tp_percent
        )

        logger.info(f"Sent pyramid added notification for {position_group.symbol} pyramid {pyramid.pyramid_index}")

    except Exception as e:
        logger.error(f"Error broadcasting pyramid added: {e}")
