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
    alert_message: Optional[str] = ""  # Optional - not needed for exit signals

class ExecutionIntent(BaseModel):
    type: Literal["signal", "exit", "reduce", "reverse"]
    side: Literal["buy", "sell", "long", "short"]
    position_size_type: Optional[Literal["contracts", "base", "quote"]] = "quote"  # Default for exits
    precision_mode: Optional[Literal["auto"]] = "auto"  # Default for exits

class RiskInfo(BaseModel):
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_slippage_percent: float

class WebhookPayload(BaseModel):
    secret: Optional[str] = None  # Optional when user has secure_signals=False
    source: str
    timestamp: datetime
    tv: TradingViewData
    strategy_info: StrategyInfo
    execution_intent: ExecutionIntent
    risk: RiskInfo

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
            uuid.UUID: lambda v: str(v),
        }

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
            uuid.UUID: lambda v: str(v),
        }