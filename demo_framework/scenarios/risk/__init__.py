"""Risk Engine Scenarios (R-001 to R-045)."""

from .validation_scenarios import (
    MaxGlobalPositionsEnforced,
    MaxPerSymbolEnforced,
    RiskCheckOnNewPosition,
    RiskCheckOnPyramid,
    RiskCheckOnQueuePromotion,
    RiskCheckPasses,
    MultipleLimitsChecked,
    RiskConfigMissingUsesDefaults,
)

from .timer_offset_scenarios import (
    TimerStartsWhenConditionsMet,
    TimerNotStartWithoutLoser,
    TimerNotStartWithoutWinner,
    OffsetCalculatesCorrectAmount,
    OffsetPartialClose,
    TimerResetsOnConditionChange,
    RiskStatusAPIReturnsAll,
    RiskEngineEnabled,
    OffsetOnlyUsesExcessProfit,
    MultipleWinnersOffsetSelection,
    MultipleLosersOffsetPriority,
    OffsetHistoryTracked,
)

__all__ = [
    # Validation scenarios (R-001 to R-010)
    "MaxGlobalPositionsEnforced",
    "MaxPerSymbolEnforced",
    "RiskCheckOnNewPosition",
    "RiskCheckOnPyramid",
    "RiskCheckOnQueuePromotion",
    "RiskCheckPasses",
    "MultipleLimitsChecked",
    "RiskConfigMissingUsesDefaults",
    # Timer/Offset scenarios (R-011 to R-022)
    "TimerStartsWhenConditionsMet",
    "TimerNotStartWithoutLoser",
    "TimerNotStartWithoutWinner",
    "OffsetCalculatesCorrectAmount",
    "OffsetPartialClose",
    "TimerResetsOnConditionChange",
    "RiskStatusAPIReturnsAll",
    "RiskEngineEnabled",
    "OffsetOnlyUsesExcessProfit",
    "MultipleWinnersOffsetSelection",
    "MultipleLosersOffsetPriority",
    "OffsetHistoryTracked",
]
