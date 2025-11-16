from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from uuid import UUID
from datetime import datetime
from typing import Literal
from enum import Enum

class PositionGroupStatus(str, Enum):
    WAITING = "waiting"
    LIVE = "live"
    PARTIALLY_FILLED = "partially_filled"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"

class TPMode(str, Enum):
    PER_LEG = "per_leg"
    AGGREGATE = "aggregate"
    HYBRID = "hybrid"

class PositionGroupSchema(BaseModel):
    id: UUID
    user_id: UUID
    exchange: str
    symbol: str
    timeframe: int
    side: Literal["long", "short"]
    status: PositionGroupStatus
    pyramid_count: int
    max_pyramids: int
    replacement_count: int
    total_dca_legs: int
    filled_dca_legs: int
    base_entry_price: Decimal
    weighted_avg_entry: Decimal
    total_invested_usd: Decimal
    total_filled_quantity: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_percent: Decimal
    realized_pnl_usd: Decimal
    tp_mode: TPMode
    tp_aggregate_percent: Decimal | None = None
    risk_timer_start: datetime | None = None
    risk_timer_expires: datetime | None = None
    risk_eligible: bool
    risk_blocked: bool
    risk_skip_once: bool
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)