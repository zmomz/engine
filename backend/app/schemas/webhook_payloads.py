from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
import uuid

class TradingViewData(BaseModel):
    exchange: str
    symbol: str
    timeframe: int
    action: str
    market_position: str
    market_position_size: float
    prev_market_position: str
    prev_market_position_size: float
    entry_price: float
    close_price: float
    order_size: float

    @field_validator('exchange', 'symbol', 'action', 'market_position', 'prev_market_position')
    @classmethod
    def no_placeholders(cls, v: str) -> str:
        if "{{" in v or "}}" in v:
             raise ValueError("Unreplaced placeholder detected")
        return v

class StrategyInfo(BaseModel):
    trade_id: str
    alert_name: str
    alert_message: str

class ExecutionIntent(BaseModel):
    type: Literal["signal", "exit", "reduce", "reverse"]
    side: Literal["buy", "sell", "long", "short"]
    position_size_type: Literal["contracts", "base", "quote"]
    precision_mode: Literal["auto"]

class RiskInfo(BaseModel):
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage_percent: float

class WebhookPayload(BaseModel):
    user_id: uuid.UUID
    secret: str
    source: str
    timestamp: datetime
    tv: TradingViewData
    strategy_info: StrategyInfo
    execution_intent: ExecutionIntent
    risk: RiskInfo

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
            uuid.UUID: lambda v: str(v),
        }

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
            uuid.UUID: lambda v: str(v),
        }