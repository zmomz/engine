from pydantic import BaseModel
from typing import Literal, Optional, List
from decimal import Decimal
from datetime import datetime

class OrderType(str): # Using str for Literal compatibility in Pydantic v2
    LIMIT = "limit"
    MARKET = "market"

class OrderStatus(str):
    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class Fill(BaseModel):
    price: Decimal
    amount: Decimal
    cost: Decimal
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    timestamp: datetime

class ExchangeOrder(BaseModel):
    id: str
    symbol: str
    type: OrderType
    side: Literal["buy", "sell"]
    price: Decimal
    amount: Decimal
    filled: Decimal = Decimal(0)
    remaining: Decimal
    status: OrderStatus
    cost: Decimal = Decimal(0)
    fee: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    timestamp: datetime
    datetime: str
    lastTradeTimestamp: Optional[datetime] = None
    trades: List[Fill] = [] # Individual fills

class Precision(BaseModel):
    amount: int  # Number of decimal places for quantity
    price: int   # Number of decimal places for price
    min_amount: Decimal
    min_notional: Decimal
