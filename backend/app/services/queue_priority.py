"""
Queue Priority Calculation Module

This module provides configurable priority calculation for queued signals.
"""

from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from app.models.queued_signal import QueuedSignal
from app.models.position_group import PositionGroup
from app.schemas.grid_config import PriorityRulesConfig


def calculate_queue_priority(
    signal: QueuedSignal, 
    active_groups: List[PositionGroup], 
    priority_config: Optional[PriorityRulesConfig] = None
) -> Decimal:
    """
    Calculate queue priority based on user-configured rules.
    Rules are applied in the order specified by priority_config.priority_order.
    
    Args:
        signal: The queued signal to calculate priority for
        active_groups: List of active position groups for pyramid detection
        priority_config: PriorityRulesConfig object (if None, uses default all-enabled config)
    
    Returns:
        Decimal priority score (higher = higher priority)
    """
    # Use default config if none provided (backward compatibility)
    if priority_config is None:
        priority_config = PriorityRulesConfig()
    
    # Calculate sub-components that can be used across tiers for tie-breaking
    time_in_queue_score = Decimal("0.0")
    if signal.queued_at:
        time_in_queue = (datetime.utcnow() - signal.queued_at).total_seconds()
        time_in_queue_score = Decimal(time_in_queue) * Decimal("0.001")

    replacement_count_score = Decimal(signal.replacement_count) * Decimal("100.0")

    loss_percent_score = Decimal("0.0")
    if signal.current_loss_percent is not None and signal.current_loss_percent < Decimal("0"):
        loss_percent_score = abs(signal.current_loss_percent) * Decimal("10000.0")

    # Rule implementations
    def check_same_pair_timeframe():
        """Check if this is a pyramid continuation of an active position"""
        is_pyramid = any(
            g.symbol == signal.symbol and
            g.exchange == signal.exchange and
            g.timeframe == signal.timeframe and
            g.side == signal.side and
            g.user_id == signal.user_id
            for g in active_groups
        )
        return is_pyramid

    def check_deepest_loss_percent():
        """Check if signal has a current loss (negative PnL)"""
        return signal.current_loss_percent is not None and signal.current_loss_percent < Decimal("0")

    def check_highest_replacement():
        """Check if signal has been replaced at least once"""
        return signal.replacement_count > 0

    # Rule checkers mapping
    rule_checkers = {
        "same_pair_timeframe": check_same_pair_timeframe,
        "deepest_loss_percent": check_deepest_loss_percent,
        "highest_replacement": check_highest_replacement,
        "fifo_fallback": lambda: True  # FIFO always applies
    }

    # Base scores for each tier (decreasing by order of magnitude)
    # These ensure proper tier separation even with tie-breakers
    tier_base_scores = {
        0: Decimal("10000000.0"),  # Tier 0 (highest priority)
        1: Decimal("1000000.0"),   # Tier 1
        2: Decimal("10000.0"),     # Tier 2
        3: Decimal("1000.0"),      # Tier 3 (lowest priority)
    }

    # Apply rules in configured order
    for tier_index, rule_name in enumerate(priority_config.priority_order):
        # Skip disabled rules
        if not priority_config.priority_rules_enabled.get(rule_name, False):
            continue
        
        # Check if this rule applies to the signal
        rule_checker = rule_checkers.get(rule_name)
        if rule_checker and rule_checker():
            # This rule applies - calculate score for this tier
            base_score = tier_base_scores[tier_index]
            
            # Add tie-breakers based on lower-priority factors
            if rule_name == "same_pair_timeframe":
                # Pyramid continuation: add loss, replacement, and FIFO as tie-breakers
                return base_score + loss_percent_score + replacement_count_score + time_in_queue_score
            elif rule_name == "deepest_loss_percent":
                # Deepest loss: add replacement and FIFO as tie-breakers
                return base_score + loss_percent_score + replacement_count_score + time_in_queue_score
            elif rule_name == "highest_replacement":
                # Replacement count: add FIFO as tie-breaker
                return base_score + replacement_count_score + time_in_queue_score
            else:  # fifo_fallback
                # FIFO: just use time in queue
                return base_score + time_in_queue_score
    
    # Fallback: if no rules apply (shouldn't happen), use FIFO
    return Decimal("1000.0") + time_in_queue_score


def explain_priority(
    signal: QueuedSignal, 
    active_groups: List[PositionGroup],
    priority_config: Optional[PriorityRulesConfig] = None
) -> str:
    """
    Generate human-readable explanation of why a signal has its priority.
    
    Args:
        signal: The queued signal
        active_groups: List of active position groups
        priority_config: Priority rules configuration
    
    Returns:
        Human-readable explanation string
    """
    if priority_config is None:
        priority_config = PriorityRulesConfig()
    
    score = calculate_queue_priority(signal, active_groups, priority_config)
    
    # Determine which rule triggered
    triggered_rules = []
    
    # Check same pair/timeframe
    is_pyramid = any(
        g.symbol == signal.symbol and
        g.exchange == signal.exchange and
        g.timeframe == signal.timeframe and
        g.side == signal.side and
        g.user_id == signal.user_id
        for g in active_groups
    )
    if is_pyramid and priority_config.priority_rules_enabled.get("same_pair_timeframe", False):
        triggered_rules.append(f"Pyramid continuation for {signal.symbol}")
    
    # Check deepest loss
    if (signal.current_loss_percent is not None and 
        signal.current_loss_percent < Decimal("0") and
        priority_config.priority_rules_enabled.get("deepest_loss_percent", False)):
        triggered_rules.append(f"Loss: {signal.current_loss_percent}%")
    
    # Check replacement count
    if signal.replacement_count > 0 and priority_config.priority_rules_enabled.get("highest_replacement", False):
        triggered_rules.append(f"{signal.replacement_count} replacements")
    
    # FIFO always applies if enabled
    if priority_config.priority_rules_enabled.get("fifo_fallback", False):
        if signal.queued_at:
            queued_duration = (datetime.utcnow() - signal.queued_at).total_seconds()
            triggered_rules.append(f"Queued for {int(queued_duration)}s")
    
    rule_explanation = ", ".join(triggered_rules) if triggered_rules else "No rules applied"
    return f"Priority: {score} ({rule_explanation})"
