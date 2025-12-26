"""
Backward compatibility re-exports for risk_engine.py.

This file maintains backward compatibility with existing imports.
The actual implementation has been split into:
- app.services.risk.risk_selector (selection algorithms)
- app.services.risk.risk_timer (timer management)
- app.services.risk.risk_executor (offset execution)
- app.services.risk.risk_engine (main orchestrator)
"""
# Re-export everything from the new location
from app.services.risk import (
    RiskEngineService,
    _check_pyramids_complete,
    _filter_eligible_losers,
    _select_top_winners,
    select_loser_and_winners,
    update_risk_timers,
    round_to_step_size,
    calculate_partial_close_quantities,
)

__all__ = [
    "RiskEngineService",
    "_check_pyramids_complete",
    "_filter_eligible_losers",
    "_select_top_winners",
    "select_loser_and_winners",
    "update_risk_timers",
    "round_to_step_size",
    "calculate_partial_close_quantities",
]
