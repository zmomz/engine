"""
Timer management for the Risk Engine.
Handles starting, resetting, and expiring risk timers for positions.
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

    - Timer RESETS (stops and clears) when:
      - A new pyramid is received (pyramid_count increases)
      - Loss threshold is no longer exceeded (price improved)
      - Pyramids are no longer complete (should not happen normally)

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

        # Both conditions must be met for timer to run
        both_conditions_met = pyramids_complete and loss_exceeded

        if both_conditions_met:
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
                if not loss_exceeded:
                    reason.append(f"loss improved ({pg.unrealized_pnl_percent}% > {config.loss_threshold_percent}%)")

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
