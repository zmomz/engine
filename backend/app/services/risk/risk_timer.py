"""
Timer management for the Risk Engine.
Handles starting, resetting, and expiring risk timers for positions.
Also handles recovery of stuck positions.
"""
import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.grid_config import RiskEngineConfig
from app.services.risk.risk_selector import _check_pyramids_complete
from app.services.telegram_signal_helper import broadcast_risk_event

logger = logging.getLogger(__name__)

# Maximum time a position can be in "closing" status before being considered stuck
# Reduced from 5 minutes to 2 minutes for faster recovery of stuck positions
CLOSING_TIMEOUT_MINUTES = 2


async def update_risk_timers(
    position_groups: List[PositionGroup],
    config: RiskEngineConfig,
    session: AsyncSession
) -> None:
    """
    Update risk timers for all positions based on current conditions.

    Timer Logic:
    - Timer STARTS when BOTH conditions are met:
      1. Required pyramids are complete (all DCAs filled)
      2. Loss threshold is exceeded

    - Timer CONTINUES running as long as:
      1. Pyramids are still complete
      2. Position is still in loss (PnL < 0), even if above threshold

    - Timer RESETS (stops and clears) when:
      - A new pyramid is received (pyramids no longer complete due to unfilled DCAs)
      - Position becomes profitable (PnL >= 0)

    Args:
        position_groups: List of active positions to check
        config: Risk engine configuration
        session: Database session for updates
    """
    now = datetime.utcnow()

    for pg in position_groups:
        if pg.status != PositionGroupStatus.ACTIVE.value:
            continue

        # Check current conditions
        pyramids_complete = _check_pyramids_complete(pg, config.required_pyramids_for_timer)
        loss_exceeded = pg.unrealized_pnl_percent <= config.loss_threshold_percent

        # For timer START: both pyramids complete AND loss exceeds threshold
        # For timer CONTINUE: pyramids complete AND loss is still negative (< 0)
        # Timer only resets on loss improvement if PnL becomes positive
        loss_still_negative = pg.unrealized_pnl_percent < 0

        should_start_timer = pyramids_complete and loss_exceeded
        should_continue_timer = pyramids_complete and loss_still_negative

        if should_start_timer or (pg.risk_timer_start is not None and should_continue_timer):
            # Start timer if not already started
            if pg.risk_timer_start is None:
                pg.risk_timer_start = now
                pg.risk_timer_expires = now + timedelta(minutes=config.post_pyramids_wait_minutes)
                pg.risk_eligible = False
                logger.info(
                    f"Risk timer STARTED for {pg.symbol} (ID: {pg.id}). "
                    f"Pyramids: {pg.pyramid_count}/{config.required_pyramids_for_timer}, "
                    f"Loss: {pg.unrealized_pnl_percent}% <= {config.loss_threshold_percent}%. "
                    f"Expires: {pg.risk_timer_expires}"
                )
                # Broadcast timer started event
                await broadcast_risk_event(
                    position_group=pg,
                    event_type="timer_started",
                    session=session,
                    loss_percent=pg.unrealized_pnl_percent,
                    loss_usd=pg.unrealized_pnl_usd,
                    timer_minutes=config.post_pyramids_wait_minutes
                )
            # Check if timer expired
            elif pg.risk_timer_expires and now >= pg.risk_timer_expires:
                if not pg.risk_eligible:  # Only broadcast once when first becoming eligible
                    pg.risk_eligible = True
                    logger.info(f"Risk timer EXPIRED for {pg.symbol} (ID: {pg.id}). Now eligible for offset.")
                    # Broadcast timer expired event
                    await broadcast_risk_event(
                        position_group=pg,
                        event_type="timer_expired",
                        session=session,
                        loss_percent=pg.unrealized_pnl_percent,
                        loss_usd=pg.unrealized_pnl_usd,
                        timer_minutes=config.post_pyramids_wait_minutes
                    )
        else:
            # Conditions not met - reset timer if it was running
            if pg.risk_timer_start is not None:
                reason = []
                if not pyramids_complete:
                    reason.append(f"pyramids incomplete ({pg.pyramid_count}/{config.required_pyramids_for_timer})")
                if not loss_still_negative:
                    reason.append(f"position became profitable ({pg.unrealized_pnl_percent}% >= 0%)")

                logger.info(
                    f"Risk timer RESET for {pg.symbol} (ID: {pg.id}). "
                    f"Reason: {', '.join(reason)}"
                )

                # Broadcast timer reset event
                await broadcast_risk_event(
                    position_group=pg,
                    event_type="timer_reset",
                    session=session,
                    loss_percent=pg.unrealized_pnl_percent,
                    loss_usd=pg.unrealized_pnl_usd
                )

            pg.risk_timer_start = None
            pg.risk_timer_expires = None
            pg.risk_eligible = False


async def recover_stuck_closing_positions(
    position_groups: List[PositionGroup],
    session: AsyncSession
) -> List[PositionGroup]:
    """
    Recover positions that are stuck in "closing" status.

    A position is considered stuck if:
    - Status is "closing"
    - It has been in "closing" status for more than CLOSING_TIMEOUT_MINUTES
    - It still has total_filled_quantity > 0 (not actually closed)

    Recovery action:
    - Revert status to "active" so the risk engine can retry

    Args:
        position_groups: List of positions to check
        session: Database session for updates

    Returns:
        List of recovered positions
    """
    now = datetime.utcnow()
    recovered = []

    logger.info(f"Checking {len(position_groups)} closing positions for recovery (timeout={CLOSING_TIMEOUT_MINUTES}min)")

    for pg in position_groups:
        if pg.status != PositionGroupStatus.CLOSING.value:
            continue

        # Check if position is stuck (in closing for too long)
        # Use closing_started_at if available, otherwise fall back to updated_at
        closing_timestamp = pg.closing_started_at or pg.updated_at
        if closing_timestamp:
            time_in_closing = now - closing_timestamp
            logger.info(f"Position {pg.symbol} in CLOSING for {time_in_closing.total_seconds():.0f}s (timeout={CLOSING_TIMEOUT_MINUTES*60}s)")
            if time_in_closing < timedelta(minutes=CLOSING_TIMEOUT_MINUTES):
                logger.info(f"Position {pg.symbol} not yet stuck - waiting for timeout")
                continue
        else:
            # If no timestamp, skip - can't determine how long it's been closing
            logger.warning(f"Position {pg.symbol} has no closing_started_at or updated_at, cannot determine closing duration")
            continue

        # Check if position still has quantity (wasn't actually closed)
        if pg.total_filled_quantity and pg.total_filled_quantity > 0:
            logger.warning(
                f"Recovering stuck closing position {pg.symbol} (ID: {pg.id}). "
                f"In closing status for {time_in_closing}. "
                f"Reverting to ACTIVE for retry."
            )

            # Revert to active status
            pg.status = PositionGroupStatus.ACTIVE.value
            # Clear risk timer so it can be re-evaluated
            pg.risk_timer_start = None
            pg.risk_timer_expires = None
            pg.risk_eligible = False

            recovered.append(pg)
        else:
            # Position has no quantity, it should be marked as closed
            logger.warning(
                f"Position {pg.symbol} (ID: {pg.id}) stuck in closing but has no quantity. "
                f"Marking as CLOSED."
            )
            pg.status = PositionGroupStatus.CLOSED.value
            pg.closed_at = now
            recovered.append(pg)

    if recovered:
        logger.info(f"Recovered {len(recovered)} stuck closing positions")

    return recovered
