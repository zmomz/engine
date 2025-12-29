"""
Pure selection logic for the Risk Engine.
Contains algorithms for filtering eligible losers and selecting top winners.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.grid_config import RiskEngineConfig


def _check_pyramids_complete(pg: PositionGroup, required_pyramids: int) -> bool:
    """
    Check if the required number of pyramids have ALL their DCAs filled.
    A pyramid is considered complete when all its DCA orders are filled.

    Args:
        pg: Position group to check
        required_pyramids: Number of pyramids that must be complete (default 3)

    Returns:
        True if at least required_pyramids have all DCAs filled
    """
    if pg.pyramid_count < required_pyramids:
        return False

    return pg.filled_dca_legs >= pg.total_dca_legs


def _filter_eligible_losers(position_groups: List[PositionGroup], config: RiskEngineConfig) -> List[PositionGroup]:
    """
    Helper to filter positions eligible for loss offset.

    A position is eligible when:
    1. Status is ACTIVE
    2. Required number of pyramids are filled (all DCAs complete)
    3. Loss threshold is exceeded
    4. Timer has expired (timer starts when conditions 2 & 3 are both met)
    5. Not blocked or skip_once flagged
    """
    eligible_losers = []
    for pg in position_groups:
        # Basic status check
        if pg.status != PositionGroupStatus.ACTIVE.value:
            continue

        # Must not be blocked or skip_once
        if pg.risk_blocked or pg.risk_skip_once:
            continue

        # Check if required pyramids are complete (all DCAs filled)
        pyramids_complete = _check_pyramids_complete(pg, config.required_pyramids_for_timer)

        # Check if loss threshold is exceeded
        loss_exceeded = pg.unrealized_pnl_percent <= config.loss_threshold_percent

        # Both conditions must be met for timer to be valid
        if not (pyramids_complete and loss_exceeded):
            continue

        # Timer must exist and be expired
        if not pg.risk_timer_expires or pg.risk_timer_expires > datetime.utcnow():
            continue

        eligible_losers.append(pg)
    return eligible_losers


def _select_top_winners(position_groups: List[PositionGroup], count: int, exclude_id: uuid.UUID = None) -> List[PositionGroup]:
    """Helper to select top profitable positions.

    Any position with unrealized profit can be a winner for offset execution,
    regardless of whether all DCAs have filled. Valid statuses include:
    LIVE, PARTIALLY_FILLED, and ACTIVE. Positions in CLOSING, CLOSED, or FAILED
    states are excluded.

    Positions with zero remaining quantity (fully hedged) are excluded.
    """
    # All "open" statuses that can participate as winners
    valid_winner_statuses = (
        PositionGroupStatus.LIVE.value,
        PositionGroupStatus.PARTIALLY_FILLED.value,
        PositionGroupStatus.ACTIVE.value,
    )
    winning_positions = [
        pg for pg in position_groups
        if pg.status in valid_winner_statuses
        and pg.unrealized_pnl_usd > 0
        and pg.total_filled_quantity > 0  # Exclude fully hedged positions
        and (exclude_id is None or pg.id != exclude_id)
    ]

    # Sort by USD profit (descending)
    winning_positions.sort(
        key=lambda pg: pg.unrealized_pnl_usd,
        reverse=True
    )

    # Take up to max_winners_to_combine
    return winning_positions[:count]


def select_loser_and_winners(
    position_groups: List[PositionGroup],
    config: RiskEngineConfig
) -> Tuple[Optional[PositionGroup], List[PositionGroup], Decimal]:
    """
    Risk Engine selection logic:

    Loser Selection (by % loss):
    1. Highest loss percentage
    2. If tied -> highest unrealized loss USD
    3. If tied -> oldest trade

    Winner Selection (by $ profit):
    - Rank all winning positions by unrealized profit USD
    - Select up to max_winners_to_combine (default: 3)
    - Exclude the loser from winner selection
    - IMPORTANT: Combined winner profit must be >= loser loss

    Offset Execution:
    - Calculate required_usd to cover loser (exact loss amount)
    - Close winners PARTIALLY to realize that exact amount
    - Never close a winner's entire position - only extract needed profit
    """
    eligible_losers = _filter_eligible_losers(position_groups, config)

    if not eligible_losers:
        return None, [], Decimal("0")

    # Sort losers by priority
    selected_loser = max(eligible_losers, key=lambda pg: (
        abs(pg.unrealized_pnl_percent),  # Primary: highest loss %
        abs(pg.unrealized_pnl_usd),      # Secondary: highest loss $
        -pg.created_at.timestamp()        # Tertiary: oldest
    ))

    # Required USD is the exact loss amount to cover
    required_usd = abs(selected_loser.unrealized_pnl_usd)

    # Select potential winners, excluding the loser
    potential_winners = _select_top_winners(
        position_groups,
        config.max_winners_to_combine,
        exclude_id=selected_loser.id
    )

    # CRITICAL: Check if combined winner profit >= loser loss
    # Only winners whose combined unrealized profit can cover the loss are valid
    combined_profit = sum(
        Decimal(str(w.unrealized_pnl_usd)) for w in potential_winners
    )

    if combined_profit < required_usd:
        # Not enough profit to offset the loss - abort offset
        return None, [], Decimal("0")

    return selected_loser, potential_winners, required_usd
