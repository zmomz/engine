from typing import List, Optional
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
    PYRAMID_AGGREGATE = "pyramid_aggregate"

class DCAOrderSchema(BaseModel):
    id: UUID
    leg_index: int
    order_type: str
    price: Decimal
    quantity: Decimal
    status: str
    filled_quantity: Decimal | None = None
    
    model_config = ConfigDict(from_attributes=True)

class PyramidSchema(BaseModel):
    id: UUID
    pyramid_index: int
    entry_price: Decimal
    status: str
    dca_orders: List[DCAOrderSchema] = []

    model_config = ConfigDict(from_attributes=True)

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
    
    pyramids: List[PyramidSchema] = []

    model_config = ConfigDict(from_attributes=True)