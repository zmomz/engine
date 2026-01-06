"""
Mock Exchange Server - Binance-compatible API
A full-featured mock exchange for testing the trading engine.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional, List
from decimal import Decimal, ROUND_DOWN

from fastapi import FastAPI, HTTPException, Depends, Request, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from database import init_db, get_db, get_db_session
from models import Symbol, Order, Balance, Position, Trade, APIKey, PriceHistory, WebhookLog
from order_matching import OrderMatchingEngine
from auth import get_api_key_from_request

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Mock Exchange",
    description="Binance-compatible mock exchange for testing",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler - returns JSON with actual error details
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return JSON with details."""
    import traceback
    error_detail = {
        "error": str(exc),
        "type": type(exc).__name__,
        "path": str(request.url.path),
        "traceback": traceback.format_exc()
    }
    logger.error(f"Unhandled exception: {error_detail}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__, "traceback": traceback.format_exc()}
    )


# ============================================================================
# Pydantic Models
# ============================================================================

class OrderRequest(BaseModel):
    symbol: str
    side: str  # BUY/SELL
    type: str  # LIMIT/MARKET
    quantity: Optional[float] = None  # Base quantity (e.g., BTC amount)
    quoteOrderQty: Optional[float] = None  # Quote quantity (e.g., USDT amount) for market orders
    price: Optional[float] = None
    stopPrice: Optional[float] = None
    timeInForce: Optional[str] = "GTC"
    reduceOnly: Optional[bool] = False
    positionSide: Optional[str] = "BOTH"
    newClientOrderId: Optional[str] = None


class PriceUpdateRequest(BaseModel):
    price: float


class WebhookPayload(BaseModel):
    user_id: str
    secret: str
    source: str = "tradingview"
    timestamp: Optional[str] = None
    tv: dict
    strategy_info: dict
    execution_intent: dict
    risk: dict


class APIKeyCreate(BaseModel):
    label: str = "Default"
    initial_balance: float = 100000.0


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    logger.info("Initializing Mock Exchange database...")
    init_db()
    logger.info("Mock Exchange ready!")


# ============================================================================
# Public Endpoints (No Auth Required) - Binance /fapi/v1 style
# ============================================================================

@app.get("/fapi/v1/ping")
async def ping():
    """Test connectivity."""
    return {}


@app.get("/fapi/v1/time")
async def server_time():
    """Get server time."""
    return {"serverTime": int(datetime.utcnow().timestamp() * 1000)}


@app.get("/fapi/v1/exchangeInfo")
async def exchange_info(db: Session = Depends(get_db)):
    """Get exchange trading rules and symbol information."""
    symbols = db.query(Symbol).all()

    symbol_list = []
    for s in symbols:
        symbol_list.append({
            "symbol": s.symbol,
            "pair": s.symbol,
            "contractType": s.contract_type,
            "deliveryDate": 4133404800000,
            "onboardDate": 1569398400000,
            "status": s.status,
            "baseAsset": s.base_asset,
            "quoteAsset": s.quote_asset,
            "marginAsset": s.margin_asset,
            "pricePrecision": len(str(s.tick_size).split('.')[-1]) if '.' in str(s.tick_size) else 0,
            "quantityPrecision": len(str(s.step_size).split('.')[-1]) if '.' in str(s.step_size) else 0,
            "baseAssetPrecision": 8,
            "quotePrecision": 8,
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": str(s.tick_size),
                    "maxPrice": "1000000",
                    "tickSize": str(s.tick_size)
                },
                {
                    "filterType": "LOT_SIZE",
                    "minQty": str(s.min_qty),
                    "maxQty": str(s.max_qty),
                    "stepSize": str(s.step_size)
                },
                {
                    "filterType": "MIN_NOTIONAL",
                    "notional": str(s.min_notional)
                }
            ]
        })

    return {
        "timezone": "UTC",
        "serverTime": int(datetime.utcnow().timestamp() * 1000),
        "rateLimits": [],
        "exchangeFilters": [],
        "symbols": symbol_list
    }


@app.get("/fapi/v1/ticker/price")
async def get_ticker_price(
    symbol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get latest price for a symbol or all symbols."""
    if symbol:
        sym = db.query(Symbol).filter(Symbol.symbol == symbol).first()
        if not sym:
            raise HTTPException(status_code=400, detail=f"Symbol {symbol} not found")
        return {
            "symbol": sym.symbol,
            "price": str(sym.current_price),
            "time": int(datetime.utcnow().timestamp() * 1000)
        }
    else:
        symbols = db.query(Symbol).all()
        return [
            {
                "symbol": s.symbol,
                "price": str(s.current_price),
                "time": int(datetime.utcnow().timestamp() * 1000)
            }
            for s in symbols
        ]


@app.get("/fapi/v1/premiumIndex")
async def get_premium_index(
    symbol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get mark price and funding rate."""
    if symbol:
        sym = db.query(Symbol).filter(Symbol.symbol == symbol).first()
        if not sym:
            raise HTTPException(status_code=400, detail=f"Symbol {symbol} not found")
        return {
            "symbol": sym.symbol,
            "markPrice": str(sym.mark_price),
            "indexPrice": str(sym.index_price),
            "lastFundingRate": "0.00010000",
            "nextFundingTime": int(datetime.utcnow().timestamp() * 1000) + 28800000,
            "time": int(datetime.utcnow().timestamp() * 1000)
        }
    else:
        symbols = db.query(Symbol).all()
        return [
            {
                "symbol": s.symbol,
                "markPrice": str(s.mark_price),
                "indexPrice": str(s.index_price),
                "lastFundingRate": "0.00010000",
                "nextFundingTime": int(datetime.utcnow().timestamp() * 1000) + 28800000,
                "time": int(datetime.utcnow().timestamp() * 1000)
            }
            for s in symbols
        ]


@app.get("/fapi/v1/depth")
async def get_order_book(
    symbol: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get order book depth."""
    sym = db.query(Symbol).filter(Symbol.symbol == symbol).first()
    if not sym:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not found")

    # Generate fake order book around current price
    price = sym.current_price
    tick = sym.tick_size

    bids = [[str(price - tick * (i + 1)), str(1.0 * (i + 1))] for i in range(min(limit, 20))]
    asks = [[str(price + tick * (i + 1)), str(1.0 * (i + 1))] for i in range(min(limit, 20))]

    return {
        "lastUpdateId": int(datetime.utcnow().timestamp() * 1000),
        "E": int(datetime.utcnow().timestamp() * 1000),
        "T": int(datetime.utcnow().timestamp() * 1000),
        "bids": bids,
        "asks": asks
    }


# ============================================================================
# Authenticated Endpoints - Binance /fapi/v1 style
# ============================================================================

@app.get("/fapi/v2/balance")
async def get_balance(
    request: Request,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Get account balance."""
    api_key = await get_api_key_from_request(request, db)

    balances = db.query(Balance).filter(Balance.api_key_id == api_key.id).all()

    if not balances:
        # Return default USDT balance
        return [{
            "accountAlias": "mock",
            "asset": "USDT",
            "balance": "100000.00000000",
            "crossWalletBalance": "100000.00000000",
            "crossUnPnl": "0.00000000",
            "availableBalance": "100000.00000000",
            "maxWithdrawAmount": "100000.00000000",
            "marginAvailable": True,
            "updateTime": int(datetime.utcnow().timestamp() * 1000)
        }]

    return [
        {
            "accountAlias": "mock",
            "asset": b.asset,
            "balance": f"{b.total:.8f}",
            "crossWalletBalance": f"{b.total:.8f}",
            "crossUnPnl": "0.00000000",
            "availableBalance": f"{b.free:.8f}",
            "maxWithdrawAmount": f"{b.free:.8f}",
            "marginAvailable": True,
            "updateTime": int(datetime.utcnow().timestamp() * 1000)
        }
        for b in balances
    ]


@app.get("/fapi/v2/account")
async def get_account(
    request: Request,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Get account information including positions."""
    api_key = await get_api_key_from_request(request, db)

    balances = db.query(Balance).filter(Balance.api_key_id == api_key.id).all()
    positions = db.query(Position).filter(Position.api_key_id == api_key.id).all()

    # Calculate totals
    total_wallet = sum(b.total for b in balances)
    total_unrealized = sum(p.unrealized_pnl for p in positions)

    assets = [
        {
            "asset": b.asset,
            "walletBalance": f"{b.total:.8f}",
            "unrealizedProfit": "0.00000000",
            "marginBalance": f"{b.total:.8f}",
            "maintMargin": "0.00000000",
            "initialMargin": f"{b.locked:.8f}",
            "positionInitialMargin": "0.00000000",
            "openOrderInitialMargin": f"{b.locked:.8f}",
            "crossWalletBalance": f"{b.free:.8f}",
            "crossUnPnl": "0.00000000",
            "availableBalance": f"{b.free:.8f}",
            "maxWithdrawAmount": f"{b.free:.8f}",
            "marginAvailable": True,
            "updateTime": int(datetime.utcnow().timestamp() * 1000)
        }
        for b in balances
    ]

    position_list = [
        {
            "symbol": p.symbol,
            "initialMargin": "0",
            "maintMargin": "0",
            "unrealizedProfit": f"{p.unrealized_pnl:.8f}",
            "positionInitialMargin": "0",
            "openOrderInitialMargin": "0",
            "leverage": str(p.leverage),
            "isolated": p.margin_type == "isolated",
            "entryPrice": f"{p.entry_price:.8f}",
            "maxNotional": "1000000",
            "positionSide": p.position_side,
            "positionAmt": f"{p.quantity:.8f}",
            "notional": f"{abs(p.quantity * p.entry_price):.8f}",
            "isolatedWallet": "0",
            "updateTime": int(p.updated_at.timestamp() * 1000) if p.updated_at else 0
        }
        for p in positions
    ]

    return {
        "feeTier": 0,
        "canTrade": True,
        "canDeposit": True,
        "canWithdraw": True,
        "updateTime": int(datetime.utcnow().timestamp() * 1000),
        "totalInitialMargin": "0.00000000",
        "totalMaintMargin": "0.00000000",
        "totalWalletBalance": f"{total_wallet:.8f}",
        "totalUnrealizedProfit": f"{total_unrealized:.8f}",
        "totalMarginBalance": f"{total_wallet + total_unrealized:.8f}",
        "totalPositionInitialMargin": "0.00000000",
        "totalOpenOrderInitialMargin": "0.00000000",
        "totalCrossWalletBalance": f"{total_wallet:.8f}",
        "totalCrossUnPnl": f"{total_unrealized:.8f}",
        "availableBalance": f"{total_wallet:.8f}",
        "maxWithdrawAmount": f"{total_wallet:.8f}",
        "assets": assets,
        "positions": position_list
    }


@app.post("/fapi/v1/order")
async def create_order(
    order_req: OrderRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Create a new order."""
    api_key = await get_api_key_from_request(request, db)

    # Validate symbol
    symbol = db.query(Symbol).filter(Symbol.symbol == order_req.symbol).first()
    if not symbol:
        raise HTTPException(status_code=400, detail={
            "code": -1121,
            "msg": f"Invalid symbol: {order_req.symbol}"
        })

    # Determine quantity - either from base quantity or calculated from quote amount
    is_quote_order = order_req.quoteOrderQty is not None and order_req.quoteOrderQty > 0

    if is_quote_order:
        # Quote-based order: calculate base quantity from quote amount / current price
        current_price = symbol.current_price
        if current_price <= 0:
            raise HTTPException(status_code=400, detail={
                "code": -1000,
                "msg": f"Cannot process quote order: invalid current price {current_price}"
            })

        # Calculate base quantity from quote amount
        raw_quantity = Decimal(str(order_req.quoteOrderQty)) / Decimal(str(current_price))

        # Round to step size
        step_size = Decimal(str(symbol.step_size))
        quantity = float((raw_quantity / step_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * step_size)

        logger.info(f"Quote order: {order_req.quoteOrderQty} USDT @ {current_price} = {quantity} {symbol.base_asset}")
    else:
        # Base quantity order
        if order_req.quantity is None or order_req.quantity <= 0:
            raise HTTPException(status_code=400, detail={
                "code": -1013,
                "msg": "Either quantity or quoteOrderQty must be provided"
            })
        quantity = order_req.quantity

    # Validate quantity
    if quantity < symbol.min_qty:
        raise HTTPException(status_code=400, detail={
            "code": -1013,
            "msg": f"Quantity {quantity} less than minimum {symbol.min_qty}"
        })

    # Create order with generated order_id
    order = Order(
        api_key_id=api_key.id,
        order_id=Order.generate_order_id(),  # Generate Binance-style numeric ID
        symbol=order_req.symbol,
        side=order_req.side.upper(),
        type=order_req.type.upper(),
        price=order_req.price or 0.0,
        quantity=quantity,
        stop_price=order_req.stopPrice or 0.0,
        time_in_force=order_req.timeInForce or "GTC",
        reduce_only=order_req.reduceOnly or False,
        position_side=order_req.positionSide or "BOTH",
        client_order_id=order_req.newClientOrderId or None,
        status="NEW"
    )
    db.add(order)
    db.flush()

    # Process market orders immediately
    if order_req.type.upper() == "MARKET":
        engine = OrderMatchingEngine(db)
        success, message = engine.process_market_order(order)
        if not success:
            raise HTTPException(status_code=400, detail={"code": -1000, "msg": message})

    db.commit()

    return {
        "orderId": order.order_id,
        "symbol": order.symbol,
        "status": order.status,
        "clientOrderId": order.client_order_id,
        "price": str(order.price),
        "avgPrice": str(order.avg_price),
        "origQty": str(order.quantity),
        "executedQty": str(order.executed_qty),
        "cumQuote": str(order.executed_qty * order.avg_price),
        "fee": str(order.cumulative_fee or 0),
        "feeCurrency": order.fee_currency or "USDT",
        "timeInForce": order.time_in_force,
        "type": order.type,
        "reduceOnly": order.reduce_only,
        "closePosition": order.close_position,
        "side": order.side,
        "positionSide": order.position_side,
        "stopPrice": str(order.stop_price),
        "workingType": "CONTRACT_PRICE",
        "priceProtect": False,
        "origType": order.type,
        "updateTime": int(datetime.utcnow().timestamp() * 1000)
    }


@app.get("/fapi/v1/order")
async def get_order(
    symbol: str,
    orderId: Optional[int] = None,
    origClientOrderId: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Get order status."""
    api_key = await get_api_key_from_request(request, db)

    query = db.query(Order).filter(
        Order.api_key_id == api_key.id,
        Order.symbol == symbol
    )

    if orderId:
        query = query.filter(Order.order_id == orderId)
    elif origClientOrderId:
        query = query.filter(Order.client_order_id == origClientOrderId)
    else:
        raise HTTPException(status_code=400, detail={
            "code": -1102,
            "msg": "Either orderId or origClientOrderId must be provided"
        })

    order = query.first()
    if not order:
        raise HTTPException(status_code=400, detail={
            "code": -2013,
            "msg": "Order does not exist"
        })

    return {
        "orderId": order.order_id,
        "symbol": order.symbol,
        "status": order.status,
        "clientOrderId": order.client_order_id,
        "price": str(order.price),
        "avgPrice": str(order.avg_price),
        "origQty": str(order.quantity),
        "executedQty": str(order.executed_qty),
        "cumQuote": str(order.executed_qty * order.avg_price),
        "timeInForce": order.time_in_force,
        "type": order.type,
        "reduceOnly": order.reduce_only,
        "closePosition": order.close_position,
        "side": order.side,
        "positionSide": order.position_side,
        "stopPrice": str(order.stop_price),
        "workingType": "CONTRACT_PRICE",
        "priceProtect": False,
        "origType": order.type,
        "time": int(order.created_at.timestamp() * 1000),
        "updateTime": int(order.updated_at.timestamp() * 1000) if order.updated_at else 0
    }


@app.get("/fapi/v1/openOrders")
async def get_open_orders(
    symbol: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Get all open orders."""
    api_key = await get_api_key_from_request(request, db)

    query = db.query(Order).filter(
        Order.api_key_id == api_key.id,
        Order.status.in_(["NEW", "PARTIALLY_FILLED"])
    )

    if symbol:
        query = query.filter(Order.symbol == symbol)

    orders = query.all()

    return [
        {
            "orderId": o.order_id,
            "symbol": o.symbol,
            "status": o.status,
            "clientOrderId": o.client_order_id,
            "price": str(o.price),
            "avgPrice": str(o.avg_price),
            "origQty": str(o.quantity),
            "executedQty": str(o.executed_qty),
            "cumQuote": str(o.executed_qty * o.avg_price),
            "fee": str(o.cumulative_fee or 0),
            "feeCurrency": o.fee_currency or "USDT",
            "timeInForce": o.time_in_force,
            "type": o.type,
            "reduceOnly": o.reduce_only,
            "closePosition": o.close_position,
            "side": o.side,
            "positionSide": o.position_side,
            "stopPrice": str(o.stop_price),
            "workingType": "CONTRACT_PRICE",
            "priceProtect": False,
            "origType": o.type,
            "time": int(o.created_at.timestamp() * 1000),
            "updateTime": int(o.updated_at.timestamp() * 1000) if o.updated_at else 0
        }
        for o in orders
    ]


@app.delete("/fapi/v1/order")
async def cancel_order(
    symbol: str,
    orderId: Optional[int] = None,
    origClientOrderId: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Cancel an order."""
    api_key = await get_api_key_from_request(request, db)

    query = db.query(Order).filter(
        Order.api_key_id == api_key.id,
        Order.symbol == symbol
    )

    if orderId:
        query = query.filter(Order.order_id == orderId)
    elif origClientOrderId:
        query = query.filter(Order.client_order_id == origClientOrderId)
    else:
        raise HTTPException(status_code=400, detail={
            "code": -1102,
            "msg": "Either orderId or origClientOrderId must be provided"
        })

    order = query.first()
    if not order:
        raise HTTPException(status_code=400, detail={
            "code": -2013,
            "msg": "Order does not exist"
        })

    if order.status not in ["NEW", "PARTIALLY_FILLED"]:
        raise HTTPException(status_code=400, detail={
            "code": -2011,
            "msg": f"Order status is {order.status}, cannot cancel"
        })

    order.status = "CANCELED"
    order.updated_at = datetime.utcnow()
    db.commit()

    return {
        "orderId": order.order_id,
        "symbol": order.symbol,
        "status": order.status,
        "clientOrderId": order.client_order_id,
        "price": str(order.price),
        "avgPrice": str(order.avg_price),
        "origQty": str(order.quantity),
        "executedQty": str(order.executed_qty),
        "cumQuote": str(order.executed_qty * order.avg_price),
        "fee": str(order.cumulative_fee or 0),
        "feeCurrency": order.fee_currency or "USDT",
        "timeInForce": order.time_in_force,
        "type": order.type,
        "reduceOnly": order.reduce_only,
        "closePosition": order.close_position,
        "side": order.side,
        "positionSide": order.position_side,
        "stopPrice": str(order.stop_price),
        "workingType": "CONTRACT_PRICE",
        "priceProtect": False,
        "origType": order.type,
        "updateTime": int(datetime.utcnow().timestamp() * 1000)
    }


@app.get("/fapi/v2/positionRisk")
async def get_position_risk(
    symbol: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db),
    x_mbx_apikey: str = Header(None, alias="X-MBX-APIKEY")
):
    """Get position information."""
    api_key = await get_api_key_from_request(request, db)

    # Update unrealized PnL first
    engine = OrderMatchingEngine(db)
    engine.update_unrealized_pnl()

    query = db.query(Position).filter(Position.api_key_id == api_key.id)

    if symbol:
        query = query.filter(Position.symbol == symbol)

    positions = query.all()

    return [
        {
            "symbol": p.symbol,
            "positionAmt": str(p.quantity),
            "entryPrice": str(p.entry_price),
            "markPrice": str(db.query(Symbol).filter(Symbol.symbol == p.symbol).first().current_price if db.query(Symbol).filter(Symbol.symbol == p.symbol).first() else 0),
            "unRealizedProfit": str(p.unrealized_pnl),
            "liquidationPrice": str(p.liquidation_price),
            "leverage": str(p.leverage),
            "maxNotionalValue": "1000000",
            "marginType": p.margin_type,
            "isolatedMargin": "0",
            "isAutoAddMargin": "false",
            "positionSide": p.position_side,
            "notional": str(abs(p.quantity * p.entry_price)),
            "isolatedWallet": "0",
            "updateTime": int(p.updated_at.timestamp() * 1000) if p.updated_at else 0
        }
        for p in positions
    ]


# ============================================================================
# Admin Endpoints (For UI Control)
# ============================================================================

@app.get("/admin/symbols")
async def admin_get_symbols(db: Session = Depends(get_db)):
    """Get all symbols with current prices."""
    symbols = db.query(Symbol).all()
    return [
        {
            "symbol": s.symbol,
            "baseAsset": s.base_asset,
            "quoteAsset": s.quote_asset,
            "currentPrice": s.current_price,
            "markPrice": s.mark_price,
            "tickSize": s.tick_size,
            "stepSize": s.step_size,
            "minQty": s.min_qty,
            "minNotional": s.min_notional,
            "lastUpdated": s.last_updated.isoformat() if s.last_updated else None
        }
        for s in symbols
    ]


@app.put("/admin/symbols/{symbol}/price")
async def admin_set_price(
    symbol: str,
    price_req: PriceUpdateRequest,
    db: Session = Depends(get_db)
):
    """Set price for a symbol and trigger order matching."""
    sym = db.query(Symbol).filter(Symbol.symbol == symbol).first()
    if not sym:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    old_price = sym.current_price
    sym.current_price = price_req.price
    sym.mark_price = price_req.price
    sym.index_price = price_req.price
    sym.last_updated = datetime.utcnow()

    # Record price history
    history = PriceHistory(symbol=symbol, price=price_req.price)
    db.add(history)

    db.commit()

    # Check if any orders should fill at this new price
    engine = OrderMatchingEngine(db)
    filled_orders = engine.check_all_pending_orders()

    # Update unrealized PnL
    engine.update_unrealized_pnl()

    return {
        "symbol": symbol,
        "oldPrice": old_price,
        "newPrice": price_req.price,
        "filledOrders": filled_orders
    }


@app.get("/admin/orders")
async def admin_get_all_orders(
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all orders (admin view)."""
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status.upper())
    if symbol:
        query = query.filter(Order.symbol == symbol)

    orders = query.order_by(Order.created_at.desc()).limit(100).all()

    return [
        {
            "id": o.id,
            "orderId": o.order_id,
            "symbol": o.symbol,
            "side": o.side,
            "type": o.type,
            "price": o.price,
            "quantity": o.quantity,
            "executedQty": o.executed_qty,
            "avgPrice": o.avg_price,
            "status": o.status,
            "createdAt": o.created_at.isoformat() if o.created_at else None,
            "updatedAt": o.updated_at.isoformat() if o.updated_at else None
        }
        for o in orders
    ]


@app.post("/admin/orders/{order_id}/fill")
async def admin_fill_order(
    order_id: str,
    fill_price: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Manually fill an order at a specified price."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        # Try by order_id int
        order = db.query(Order).filter(Order.order_id == int(order_id)).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in ["NEW", "PARTIALLY_FILLED"]:
        raise HTTPException(status_code=400, detail=f"Order status is {order.status}, cannot fill")

    # Use provided price or order price or current market price
    if fill_price is None:
        if order.price > 0:
            fill_price = order.price
        else:
            sym = db.query(Symbol).filter(Symbol.symbol == order.symbol).first()
            fill_price = sym.current_price if sym else 0

    engine = OrderMatchingEngine(db)
    success, message = engine._fill_order(order, fill_price, order.quantity - order.executed_qty)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {
        "orderId": order.order_id,
        "status": order.status,
        "fillPrice": fill_price,
        "executedQty": order.executed_qty,
        "message": message
    }


@app.get("/admin/positions")
async def admin_get_positions(db: Session = Depends(get_db)):
    """Get all positions (admin view)."""
    # Update PnL first
    engine = OrderMatchingEngine(db)
    engine.update_unrealized_pnl()

    positions = db.query(Position).all()

    return [
        {
            "id": p.id,
            "symbol": p.symbol,
            "positionSide": p.position_side,
            "quantity": p.quantity,
            "entryPrice": p.entry_price,
            "unrealizedPnl": p.unrealized_pnl,
            "realizedPnl": p.realized_pnl,
            "leverage": p.leverage,
            "marginType": p.margin_type,
            "updatedAt": p.updated_at.isoformat() if p.updated_at else None
        }
        for p in positions
    ]


@app.get("/admin/balances")
async def admin_get_balances(db: Session = Depends(get_db)):
    """Get all balances (admin view)."""
    balances = db.query(Balance).all()

    return [
        {
            "id": b.id,
            "apiKeyId": b.api_key_id,
            "asset": b.asset,
            "free": b.free,
            "locked": b.locked,
            "total": b.total
        }
        for b in balances
    ]


@app.put("/admin/balances/{balance_id}")
async def admin_update_balance(
    balance_id: str,
    free: Optional[float] = None,
    locked: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Update a balance."""
    balance = db.query(Balance).filter(Balance.id == balance_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")

    if free is not None:
        balance.free = free
    if locked is not None:
        balance.locked = locked
    balance.total = balance.free + balance.locked

    db.commit()

    return {
        "id": balance.id,
        "asset": balance.asset,
        "free": balance.free,
        "locked": balance.locked,
        "total": balance.total
    }


@app.get("/admin/api-keys")
async def admin_get_api_keys(db: Session = Depends(get_db)):
    """Get all API keys."""
    keys = db.query(APIKey).all()

    return [
        {
            "id": k.id,
            "apiKey": k.api_key,
            "apiSecret": k.api_secret,
            "label": k.label,
            "isActive": k.is_active,
            "permissions": k.permissions,
            "createdAt": k.created_at.isoformat() if k.created_at else None
        }
        for k in keys
    ]


@app.post("/admin/api-keys")
async def admin_create_api_key(
    key_req: APIKeyCreate,
    db: Session = Depends(get_db)
):
    """Create a new API key with initial balance."""
    import secrets

    api_key = APIKey(
        api_key=f"mock_{secrets.token_hex(16)}",
        api_secret=secrets.token_hex(32),
        label=key_req.label,
        is_active=True,
        permissions="SPOT,FUTURES"
    )
    db.add(api_key)
    db.flush()

    # Add initial USDT balance
    balance = Balance(
        api_key_id=api_key.id,
        asset="USDT",
        free=key_req.initial_balance,
        locked=0.0,
        total=key_req.initial_balance
    )
    db.add(balance)
    db.commit()

    return {
        "id": api_key.id,
        "apiKey": api_key.api_key,
        "apiSecret": api_key.api_secret,
        "label": api_key.label,
        "initialBalance": key_req.initial_balance
    }


@app.delete("/admin/reset")
async def admin_reset(db: Session = Depends(get_db)):
    """Reset all data except symbols and API keys."""
    db.query(Trade).delete()
    db.query(Order).delete()
    db.query(Position).delete()
    db.query(PriceHistory).delete()
    db.query(WebhookLog).delete()

    # Reset balances to initial state
    balances = db.query(Balance).all()
    for b in balances:
        b.free = 100000.0
        b.locked = 0.0
        b.total = 100000.0

    db.commit()

    return {"message": "Exchange reset complete", "timestamp": datetime.utcnow().isoformat()}


# ============================================================================
# Mock TradingView Webhook Sender
# ============================================================================

@app.post("/admin/webhook/send")
async def admin_send_webhook(
    payload: WebhookPayload,
    target_url: str = Query(default="http://app:8000/api/v1/webhooks/{user_id}/tradingview"),
    db: Session = Depends(get_db)
):
    """Send a mock TradingView webhook to the engine."""
    # Build the full URL
    url = target_url.format(user_id=payload.user_id)

    # Add timestamp if not provided
    if not payload.timestamp:
        payload_dict = payload.dict()
        payload_dict["timestamp"] = datetime.utcnow().isoformat()
    else:
        payload_dict = payload.dict()

    # Send the webhook
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload_dict)
            response_body = response.text

            # Log the webhook
            log = WebhookLog(
                payload=json.dumps(payload_dict),
                response_status=response.status_code,
                response_body=response_body[:1000],  # Truncate if too long
                target_url=url
            )
            db.add(log)
            db.commit()

            return {
                "success": response.status_code < 400,
                "statusCode": response.status_code,
                "response": response_body[:500],
                "sentPayload": payload_dict
            }
        except Exception as e:
            # Log the error
            log = WebhookLog(
                payload=json.dumps(payload_dict),
                response_status=0,
                response_body=str(e),
                target_url=url
            )
            db.add(log)
            db.commit()

            return {
                "success": False,
                "error": str(e),
                "sentPayload": payload_dict
            }


@app.get("/admin/webhook/logs")
async def admin_get_webhook_logs(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get webhook send logs."""
    logs = db.query(WebhookLog).order_by(WebhookLog.created_at.desc()).limit(limit).all()

    return [
        {
            "id": l.id,
            "payload": json.loads(l.payload) if l.payload else None,
            "responseStatus": l.response_status,
            "responseBody": l.response_body,
            "targetUrl": l.target_url,
            "createdAt": l.created_at.isoformat() if l.created_at else None
        }
        for l in logs
    ]


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "mock-exchange"}


# ============================================================================
# Static Files (UI)
# ============================================================================

# Mount static files for UI
UI_DIR = os.path.join(os.path.dirname(__file__), "ui")
if os.path.exists(UI_DIR):
    app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_ui():
        """Serve the main UI."""
        index_path = os.path.join(UI_DIR, "index.html")
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(content="<h1>Mock Exchange</h1><p>UI not found</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
