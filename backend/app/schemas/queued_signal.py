from pydantic import BaseModel, ConfigDict, field_validator
from decimal import Decimal
from uuid import UUID
from datetime import datetime
from typing import Literal
from enum import Enum

class QueueStatus(str, Enum):
    QUEUED = "queued"
    PROMOTED = "promoted"
    CANCELLED = "cancelled"

class QueuedSignalSchema(BaseModel):
    id: UUID
    user_id: UUID
    exchange: str
    symbol: str
    timeframe: int
    side: Literal["long", "short"]
    entry_price: Decimal
    signal_payload: dict
    queued_at: datetime
    replacement_count: int
    priority_score: Decimal | None = Decimal("0")
    is_pyramid_continuation: bool
    current_loss_percent: Decimal | None = None
    priority_explanation: str | None = None
    status: QueueStatus
    promoted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('priority_score', mode='before')
    @classmethod
    def set_priority_score_default(cls, v):
        return v or Decimal("0")