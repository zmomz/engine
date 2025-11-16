from pydantic import BaseModel
from decimal import Decimal
from typing import Literal

class TradingViewSignal(BaseModel):
    """
    Pydantic model for parsing incoming TradingView webhooks.
    """
    signal_id: str
    symbol: str
    timeframe: int
    side: Literal["long", "short"]
    price: Decimal
    user_id: str
