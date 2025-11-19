
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid

app = FastAPI()

# In-memory "database" for orders
mock_db = {}

class Order(BaseModel):
    id: Optional[str] = None
    symbol: str
    side: str
    type: str
    price: float
    quantity: float
    status: str = "open"

@app.get("/orders", response_model=List[Order])
async def get_all_orders():
    return list(mock_db.values())

@app.post("/orders", response_model=Order)
async def create_order(order: Order):
    order.id = str(uuid.uuid4())
    mock_db[order.id] = order
    return order

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    if order_id not in mock_db:
        raise HTTPException(status_code=404, detail="Order not found")
    return mock_db[order_id]

@app.delete("/orders/{order_id}", response_model=Order)
async def cancel_order(order_id: str):
    if order_id not in mock_db:
        raise HTTPException(status_code=404, detail="Order not found")
    mock_db[order_id].status = "canceled"
    return mock_db[order_id]

@app.get("/symbols/{symbol}/price")
async def get_price(symbol: str):
    # Return a dummy price for any symbol
    return {"symbol": symbol, "price": 50000.00}

@app.get("/symbols/{symbol}/precision")
async def get_precision(symbol: str):
    # Return dummy precision rules
    return {
        "symbol": symbol,
        "tick_size": 0.01,
        "step_size": 0.001,
        "min_qty": 0.001,
        "min_notional": 10.0,
    }

@app.get("/balance")
async def get_balance():
    # Return a dummy balance
    return {"USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0}}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Test-only endpoints for TDD
@app.get("/test/orders", response_model=List[Order], include_in_schema=False)
async def get_test_orders():
    """Returns all orders in the mock_db for testing purposes."""
    return list(mock_db.values())

@app.delete("/test/orders", status_code=204, include_in_schema=False)
async def clear_test_orders():
    """Clears all orders from the mock_db for testing purposes."""
    mock_db.clear()
    return {}
