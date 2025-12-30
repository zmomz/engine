"""Queue System Scenarios (Q-001 to Q-040)."""

from .operations_scenarios import (
    SignalQueuedWhenPoolFull,
    SignalReplacementIncrementsCount,
    ReplacementPreservesQueueTime,
    ReplacementUpdatesPrice,
    GetQueuedSignalsReturnsAll,
    QueueSortedByPriority,
    RemoveSignalFromQueue,
    ExitCancelsMatchingQueued,
    QueueHistoryTracksPromoted,
    ManualPromotionViaAPI,
    ManualPromotionFailsNoSlot,
)

from .priority_scenarios import (
    PyramidGetsHighestPriority,
    ReplacementCountBoostsPriority,
    FIFOWithEqualPriority,
    PriorityScoreCalculation,
    AutoPromotionOnSlotFree,
    PyramidPriorityOverNewEntry,
    PromotionSelectsHighestPriority,
    QueueMaxCapacity,
    QueueStatePersistence,
    QueueConcurrentAccess,
)

__all__ = [
    # Operations scenarios (Q-001 to Q-015)
    "SignalQueuedWhenPoolFull",
    "SignalReplacementIncrementsCount",
    "ReplacementPreservesQueueTime",
    "ReplacementUpdatesPrice",
    "GetQueuedSignalsReturnsAll",
    "QueueSortedByPriority",
    "RemoveSignalFromQueue",
    "ExitCancelsMatchingQueued",
    "QueueHistoryTracksPromoted",
    "ManualPromotionViaAPI",
    "ManualPromotionFailsNoSlot",
    # Priority scenarios (Q-016 to Q-025)
    "PyramidGetsHighestPriority",
    "ReplacementCountBoostsPriority",
    "FIFOWithEqualPriority",
    "PriorityScoreCalculation",
    "AutoPromotionOnSlotFree",
    "PyramidPriorityOverNewEntry",
    "PromotionSelectsHighestPriority",
    "QueueMaxCapacity",
    "QueueStatePersistence",
    "QueueConcurrentAccess",
]
