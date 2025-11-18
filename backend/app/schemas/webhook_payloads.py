from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
import uuid

class TradingViewData(BaseModel):
    exchange: str = Field(..., alias="tv.exchange")
    symbol: str = Field(..., alias="tv.symbol")
    timeframe: int = Field(..., alias="tv.timeframe")
    action: str = Field(..., alias="tv.action")
    market_position: str = Field(..., alias="tv.market_position")
    market_position_size: float = Field(..., alias="tv.market_position_size")
    prev_market_position: str = Field(..., alias="tv.prev_market_position")
    prev_market_position_size: float = Field(..., alias="tv.prev_market_position_size")
    entry_price: float = Field(..., alias="tv.entry_price")
    close_price: float = Field(..., alias="tv.close_price")
    order_size: float = Field(..., alias="tv.order_size")

class StrategyInfo(BaseModel):
    trade_id: str = Field(..., alias="strategy_info.trade_id")
    alert_name: str = Field(..., alias="strategy_info.alert_name")
    alert_message: str = Field(..., alias="strategy_info.alert_message")

class ExecutionIntent(BaseModel):
    type: Literal["signal", "exit", "reduce", "reverse"] = Field(..., alias="execution_intent.type")
    side: Literal["buy", "sell", "long", "short"] = Field(..., alias="execution_intent.side")
    position_size_type: Literal["contracts", "base", "quote"] = Field(..., alias="execution_intent.position_size_type")
    precision_mode: Literal["auto"] = Field(..., alias="execution_intent.precision_mode")

class RiskInfo(BaseModel):
    stop_loss: Optional[float] = Field(None, alias="risk.stop_loss")
    take_profit: Optional[float] = Field(None, alias="risk.take_profit")
    max_slippage_percent: float = Field(..., alias="risk.max_slippage_percent")

class WebhookPayload(BaseModel):
    user_id: uuid.UUID
    secret: str
    source: str
    timestamp: datetime
    tv: TradingViewData = Field(..., alias="tv")
    strategy_info: StrategyInfo = Field(..., alias="strategy_info")
    execution_intent: ExecutionIntent = Field(..., alias="execution_intent")
    risk: RiskInfo = Field(..., alias="risk")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v),
            uuid.UUID: lambda v: str(v),
        }