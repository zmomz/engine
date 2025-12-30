"""
Webhook payload builders for trading signals.

Provides consistent, typed payload construction for TradingView-style webhooks.
"""

import time
from datetime import datetime
from typing import Dict, Optional


def build_webhook_payload(
    user_id: str,
    secret: str,
    symbol: str,
    action: str,
    market_position: str,
    position_size: float,
    entry_price: float,
    prev_market_position: str = "flat",
    prev_position_size: float = 0,
    trade_id: Optional[str] = None,
    alert_name: Optional[str] = None,
    alert_message: Optional[str] = None,
    timeframe: int = 60,
    exchange: str = "mock",
    position_size_type: str = "quote",
    max_slippage_percent: float = 1.0,
) -> Dict:
    """
    Build a TradingView-style webhook payload for entry signals.

    Args:
        user_id: User UUID for webhook authentication
        secret: Webhook secret for signature validation
        symbol: Trading symbol (e.g., "SOLUSDT" or "SOL/USDT")
        action: "buy" or "sell"
        market_position: Current position state ("long", "short", "flat")
        position_size: Size of the position
        entry_price: Entry price for the signal
        prev_market_position: Previous position state
        prev_position_size: Previous position size
        trade_id: Unique trade identifier (auto-generated if not provided)
        alert_name: Name of the alert
        alert_message: Alert message
        timeframe: Timeframe in minutes (default: 60)
        exchange: Exchange name (default: "mock")
        position_size_type: "quote" (USD) or "contracts" (base currency)
        max_slippage_percent: Maximum allowed slippage

    Returns:
        Dict payload ready for webhook submission
    """
    # Normalize symbol format (ensure has slash for tv.symbol)
    normalized_symbol = symbol.replace("USDT", "/USDT") if "/" not in symbol else symbol

    # Generate trade ID if not provided
    if not trade_id:
        trade_id = f"demo_{symbol.replace('/', '')}_{int(time.time())}"

    return {
        "user_id": user_id,
        "secret": secret,
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": exchange,
            "symbol": normalized_symbol,
            "timeframe": timeframe,
            "action": action,
            "market_position": market_position,
            "market_position_size": position_size,
            "prev_market_position": prev_market_position,
            "prev_market_position_size": prev_position_size,
            "entry_price": entry_price,
            "close_price": entry_price,
            "order_size": position_size,
        },
        "strategy_info": {
            "trade_id": trade_id,
            "alert_name": alert_name or f"Demo {symbol}",
            "alert_message": alert_message or f"Demo signal for {symbol}",
        },
        "execution_intent": {
            "type": "signal",
            "side": action,
            "position_size_type": position_size_type,
            "precision_mode": "auto",
        },
        "risk": {
            "max_slippage_percent": max_slippage_percent,
        },
    }


def build_entry_payload(
    user_id: str,
    secret: str,
    symbol: str,
    position_size: float,
    entry_price: float,
    side: str = "long",
    timeframe: int = 60,
    exchange: str = "mock",
    position_size_type: str = "quote",
    trade_id: Optional[str] = None,
) -> Dict:
    """
    Build a simplified entry signal payload.

    For SPOT trading: All entries are "long" positions (buy to enter).

    Args:
        user_id: User UUID
        secret: Webhook secret
        symbol: Trading symbol
        position_size: Size in USD or contracts
        entry_price: Entry price
        side: Always "long" for spot trading
        timeframe: Timeframe in minutes
        exchange: Exchange name
        position_size_type: "quote" or "contracts"
        trade_id: Optional trade ID

    Returns:
        Entry signal payload
    """
    # For SPOT trading: Always use "buy" to enter (long positions only)
    action = "buy"
    return build_webhook_payload(
        user_id=user_id,
        secret=secret,
        symbol=symbol,
        action=action,
        market_position=side,
        position_size=position_size,
        entry_price=entry_price,
        prev_market_position="flat",
        prev_position_size=0,
        timeframe=timeframe,
        exchange=exchange,
        position_size_type=position_size_type,
        trade_id=trade_id or f"entry_{symbol.replace('/', '')}_{int(time.time())}",
    )


def build_pyramid_payload(
    user_id: str,
    secret: str,
    symbol: str,
    position_size: float,
    entry_price: float,
    prev_position_size: float,
    side: str = "long",
    timeframe: int = 60,
    exchange: str = "mock",
    position_size_type: str = "quote",
    trade_id: Optional[str] = None,
) -> Dict:
    """
    Build a pyramid signal payload (add to existing position).

    For SPOT trading: Pyramids add to "long" positions (buy more).
    Detected when prev_market_position matches market_position (both "long").

    Args:
        user_id: User UUID
        secret: Webhook secret
        symbol: Trading symbol
        position_size: Size to add
        entry_price: Entry price for this pyramid
        prev_position_size: Size of the existing position
        side: Always "long" for spot trading
        timeframe: Timeframe in minutes
        exchange: Exchange name
        position_size_type: "quote" or "contracts"
        trade_id: Optional trade ID

    Returns:
        Pyramid signal payload
    """
    # For SPOT trading: Always use "buy" to add to position (long only)
    action = "buy"
    return build_webhook_payload(
        user_id=user_id,
        secret=secret,
        symbol=symbol,
        action=action,
        market_position=side,  # Same as prev (continuation)
        position_size=position_size,
        entry_price=entry_price,
        prev_market_position=side,  # Same as current (continuation)
        prev_position_size=prev_position_size,
        timeframe=timeframe,
        exchange=exchange,
        position_size_type=position_size_type,
        trade_id=trade_id or f"pyramid_{symbol.replace('/', '')}_{int(time.time())}",
    )


def build_exit_payload(
    user_id: str,
    secret: str,
    symbol: str,
    prev_position_size: float,
    exit_price: float = 0,
    side: str = "long",
    timeframe: int = 60,
    exchange: str = "mock",
    trade_id: Optional[str] = None,
) -> Dict:
    """
    Build an exit signal payload (close position).

    For SPOT trading: Exit signals sell to close long positions.
    Detected when market_position is "flat" and prev_market_position was "long".

    Args:
        user_id: User UUID
        secret: Webhook secret
        symbol: Trading symbol
        prev_position_size: Size of the position being closed
        exit_price: Exit price (used for close_price in payload)
        side: Always "long" for spot trading (the position being closed)
        timeframe: Timeframe in minutes
        exchange: Exchange name
        trade_id: Optional trade ID

    Returns:
        Exit signal payload
    """
    # For SPOT trading: Always use "sell" to exit (closing long positions)
    action = "sell"

    # Normalize symbol format
    normalized_symbol = symbol.replace("USDT", "/USDT") if "/" not in symbol else symbol

    # Generate trade ID if not provided
    if not trade_id:
        trade_id = f"exit_{symbol.replace('/', '')}_{int(time.time())}"

    # Build exit payload directly (not through build_webhook_payload)
    # because exits have different structure requirements
    return {
        "user_id": user_id,
        "secret": secret,
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": exchange,
            "symbol": normalized_symbol,
            "timeframe": timeframe,
            "action": action,
            "market_position": "flat",  # Exiting to flat
            "market_position_size": 0,  # No position after exit
            "prev_market_position": side,  # Was in position
            "prev_market_position_size": prev_position_size,
            "entry_price": exit_price,
            "close_price": exit_price,
            "order_size": prev_position_size,  # Closing entire position
        },
        "strategy_info": {
            "trade_id": trade_id,
            "alert_name": f"Exit {normalized_symbol}",
            "alert_message": f"Exit signal for {normalized_symbol}",
        },
        "execution_intent": {
            "type": "exit",  # Explicitly mark as exit
            "side": action,
            "position_size_type": "quote",
            "precision_mode": "auto",
        },
        "risk": {
            "max_slippage_percent": 1.0,
        },
    }


def build_invalid_payload(
    missing_field: Optional[str] = None,
    invalid_action: bool = False,
    wrong_secret: bool = False,
    malformed: bool = False,
) -> Dict:
    """
    Build an intentionally invalid payload for testing error handling.

    Args:
        missing_field: Remove this field from the payload
        invalid_action: Use an invalid action value
        wrong_secret: Use an incorrect secret
        malformed: Return a non-dict value

    Returns:
        Invalid payload for testing
    """
    if malformed:
        return "not a valid json object"  # type: ignore

    payload = {
        "user_id": "test-user-id",
        "secret": "wrong_secret" if wrong_secret else "test-secret",
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "mock",
            "symbol": "TEST/USDT",
            "timeframe": 60,
            "action": "hold" if invalid_action else "buy",
            "market_position": "long",
            "market_position_size": 100,
            "prev_market_position": "flat",
            "prev_market_position_size": 0,
            "entry_price": 100.0,
            "close_price": 100.0,
            "order_size": 100,
        },
        "strategy_info": {
            "trade_id": "test_invalid",
            "alert_name": "Invalid Test",
            "alert_message": "Testing invalid payload",
        },
        "execution_intent": {
            "type": "signal",
            "side": "buy",
            "position_size_type": "quote",
            "precision_mode": "auto",
        },
        "risk": {
            "max_slippage_percent": 1.0,
        },
    }

    if missing_field:
        # Remove field from appropriate location
        if missing_field in payload:
            del payload[missing_field]
        elif missing_field in payload.get("tv", {}):
            del payload["tv"][missing_field]
        elif missing_field in payload.get("strategy_info", {}):
            del payload["strategy_info"][missing_field]

    return payload
