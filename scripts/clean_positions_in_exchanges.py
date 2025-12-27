#!/usr/bin/env python3

"""
Cancel all open orders, sell all assets to USDT, and close positions on:
- Binance Spot Testnet
- Bybit (Unified Trading Account)
"""

import time
import hmac
import hashlib
import requests
import urllib.parse
import json
import asyncio
import ccxt.async_support as ccxt

# ===========================
# BINANCE TESTNET CONFIG
# ===========================
BINANCE_API_KEY = "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU"
BINANCE_API_SECRET = "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L".encode()
BINANCE_BASE_URL = "https://testnet.binance.vision"

# ===========================
# BYBIT CONFIG
# ===========================
BYBIT_API_KEY = "yJIGPFqyMqcxnYLPn3"
BYBIT_API_SECRET = "Fvucd6ZKYBRC7oGULuED0pHLKpEsxdpB2gsb"
BYBIT_BASE_URL = "https://api-testnet.bybit.com"

# Coins to skip (stablecoins)
SKIP_COINS = {'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USD'}
MIN_VALUE_USDT = 1.0

# ========================================
# BINANCE FUNCTIONS
# ========================================

def sign_binance_params(params: dict):
    query = urllib.parse.urlencode(params)
    signature = hmac.new(BINANCE_API_SECRET, query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature
    return params

def binance_signed_request(method, endpoint, params=None):
    if params is None:
        params = {}

    params["timestamp"] = int(time.time() * 1000)
    params = sign_binance_params(params)

    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}

    url = BINANCE_BASE_URL + endpoint
    if method == "GET":
        r = requests.get(url, headers=headers, params=params)
    elif method == "DELETE":
        r = requests.delete(url, headers=headers, params=params)
    else:
        raise ValueError("Unsupported HTTP method")

    if r.status_code != 200:
        print(f"Binance Error: {r.status_code} - {r.text}")
        return None
    return r.json()

def cancel_binance_orders():
    print("=" * 50)
    print("BINANCE TESTNET - Cancelling Orders")
    print("=" * 50)
    
    open_orders = binance_signed_request("GET", "/api/v3/openOrders")
    
    if open_orders is None:
        print("✗ Failed to fetch open orders\n")
        return

    if not open_orders:
        print("✓ No open orders found\n")
        return

    print(f"Found {len(open_orders)} open order(s):\n")
    
    for order in open_orders:
        print(f"  Symbol: {order['symbol']}, OrderId: {order['orderId']}, "
              f"Side: {order['side']}, Price: {order['price']}, Qty: {order['origQty']}")
    
    print("\nCancelling all orders...\n")
    
    symbols_with_orders = set(order['symbol'] for order in open_orders)
    
    for symbol in symbols_with_orders:
        result = binance_signed_request("DELETE", "/api/v3/openOrders", {"symbol": symbol})
        if result:
            print(f"  ✓ Cancelled all orders for {symbol}")
        else:
            print(f"  ✗ Failed to cancel orders for {symbol}")
    
    print()

# ========================================
# BYBIT FUNCTIONS
# ========================================

def sign_bybit_request(params: dict, timestamp: str, recv_window: str):
    """
    Generate signature for Bybit API v5
    For GET requests: timestamp + api_key + recv_window + queryString
    For POST requests: timestamp + api_key + recv_window + jsonBody
    """
    # Sort parameters for GET requests
    if params:
        param_str = urllib.parse.urlencode(sorted(params.items()))
    else:
        param_str = ""
    
    # Construct the signature payload
    signature_payload = timestamp + BYBIT_API_KEY + recv_window + param_str
    
    signature = hmac.new(
        BYBIT_API_SECRET.encode('utf-8'),
        signature_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature

def sign_bybit_request_post(json_body: str, timestamp: str, recv_window: str):
    """
    Generate signature for Bybit API v5 POST requests
    """
    signature_payload = timestamp + BYBIT_API_KEY + recv_window + json_body
    
    signature = hmac.new(
        BYBIT_API_SECRET.encode('utf-8'),
        signature_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature

def bybit_request(method, endpoint, params=None):
    if params is None:
        params = {}
    
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    
    if method == "GET":
        signature = sign_bybit_request(params, timestamp, recv_window)
        
        headers = {
            "X-BAPI-API-KEY": BYBIT_API_KEY,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
        }
        
        url = BYBIT_BASE_URL + endpoint
        r = requests.get(url, headers=headers, params=params)
        
    elif method == "POST":
        json_body = json.dumps(params)
        signature = sign_bybit_request_post(json_body, timestamp, recv_window)
        
        headers = {
            "X-BAPI-API-KEY": BYBIT_API_KEY,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }
        
        url = BYBIT_BASE_URL + endpoint
        r = requests.post(url, headers=headers, data=json_body)
        
    else:
        raise ValueError("Unsupported HTTP method")
    
    if r.status_code != 200:
        print(f"Bybit Error: {r.status_code} - {r.text}")
        return None
    
    try:
        return r.json()
    except:
        print(f"Failed to parse response: {r.text}")
        return None

def cancel_bybit_orders():
    print("=" * 50)
    print("BYBIT TESTNET - Cancelling Spot Orders")
    print("=" * 50)
    
    print("\nChecking SPOT orders...")
    
    # First, let's try to get open orders
    result = bybit_request("GET", "/v5/order/realtime", {
        "category": "spot"
    })
    
    if result and result.get("retCode") == 0:
        orders = result.get("result", {}).get("list", [])
        if orders:
            print(f"  Found {len(orders)} open spot order(s):")
            for order in orders:
                print(f"    OrderId: {order.get('orderId')}, Symbol: {order.get('symbol')}")
            
            print("\n  Cancelling all spot orders...")
            
            # Cancel each order individually
            for order in orders:
                cancel_result = bybit_request("POST", "/v5/order/cancel", {
                    "category": "spot",
                    "symbol": order.get('symbol'),
                    "orderId": order.get('orderId')
                })
                
                if cancel_result and cancel_result.get("retCode") == 0:
                    print(f"    ✓ Cancelled order {order.get('orderId')} for {order.get('symbol')}")
                else:
                    error_msg = cancel_result.get("retMsg") if cancel_result else "Unknown error"
                    print(f"    ✗ Failed to cancel order {order.get('orderId')}: {error_msg}")
        else:
            print(f"  ✓ No open orders in spot")
    else:
        error_msg = result.get("retMsg") if result else "Unknown error"
        print(f"  ✗ Failed to fetch spot orders: {error_msg}")
    
    print()

def close_bybit_positions():
    # Spot doesn't have positions, only derivatives do
    # Skipping position closure for spot testnet
    pass

# ========================================
# SELL ALL ASSETS TO USDT (ASYNC)
# ========================================

async def sell_all_binance_async():
    print("\n" + "=" * 50)
    print("BINANCE - Selling all assets to USDT")
    print("=" * 50)

    exchange = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_API_SECRET.decode() if isinstance(BINANCE_API_SECRET, bytes) else BINANCE_API_SECRET,
        'enableRateLimit': True,
        'options': {'adjustForTimeDifference': True, 'recvWindow': 20000}
    })
    exchange.set_sandbox_mode(True)

    try:
        await exchange.load_markets()
        balance = await exchange.fetch_balance()

        sold_count = 0
        skipped_count = 0

        for currency, amounts in balance.items():
            if currency in ['info', 'free', 'used', 'total', 'datetime', 'timestamp']:
                continue
            if currency in SKIP_COINS:
                continue

            if isinstance(amounts, dict):
                free = float(amounts.get('free', 0) or 0)
                if free <= 0:
                    continue

                symbol = f"{currency}/USDT"

                if symbol not in exchange.markets:
                    skipped_count += 1
                    continue

                try:
                    ticker = await exchange.fetch_ticker(symbol)
                    price = ticker.get('last', 0)
                    value_usdt = free * price if price else 0

                    if value_usdt < MIN_VALUE_USDT:
                        skipped_count += 1
                        continue

                    market = exchange.markets[symbol]
                    sell_amount = float(exchange.amount_to_precision(symbol, free))
                    min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)

                    if sell_amount < (min_amount or 0):
                        skipped_count += 1
                        continue

                    print(f"  Selling {sell_amount} {currency} (~${value_usdt:.2f})...")
                    order = await exchange.create_market_sell_order(symbol, sell_amount)
                    print(f"  ✓ Sold {currency}")
                    sold_count += 1

                except Exception as e:
                    print(f"  ✗ Failed to sell {currency}: {e}")

        print(f"\nBinance: Sold {sold_count} assets, skipped {skipped_count}")

    except Exception as e:
        print(f"Binance error: {e}")
    finally:
        await exchange.close()


async def sell_all_bybit_async():
    print("\n" + "=" * 50)
    print("BYBIT - Selling all assets to USDT")
    print("=" * 50)

    exchange = ccxt.bybit({
        'apiKey': BYBIT_API_KEY,
        'secret': BYBIT_API_SECRET,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
            'recvWindow': 20000,
            'defaultType': 'spot',
        }
    })
    exchange.set_sandbox_mode(True)

    try:
        await exchange.load_markets()

        balance = None
        for account_type in ['UNIFIED', 'SPOT', None]:
            try:
                params = {'accountType': account_type} if account_type else {}
                balance = await exchange.fetch_balance(params)
                break
            except Exception:
                continue

        if not balance:
            print("  ✗ Could not fetch balance")
            return

        sold_count = 0
        skipped_count = 0

        for currency, amounts in balance.items():
            if currency in ['info', 'free', 'used', 'total', 'datetime', 'timestamp']:
                continue
            if currency in SKIP_COINS:
                continue

            if isinstance(amounts, dict):
                free = float(amounts.get('free', 0) or 0)
                if free <= 0:
                    continue

                symbol = f"{currency}/USDT"

                if symbol not in exchange.markets:
                    skipped_count += 1
                    continue

                try:
                    ticker = await exchange.fetch_ticker(symbol)
                    price = ticker.get('last', 0)
                    value_usdt = free * price if price else 0

                    if value_usdt < MIN_VALUE_USDT:
                        skipped_count += 1
                        continue

                    market = exchange.markets[symbol]
                    sell_amount = float(exchange.amount_to_precision(symbol, free))
                    min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)

                    if sell_amount < (min_amount or 0):
                        skipped_count += 1
                        continue

                    print(f"  Selling {sell_amount} {currency} (~${value_usdt:.2f})...")
                    order = await exchange.create_market_sell_order(symbol, sell_amount)
                    print(f"  ✓ Sold {currency}")
                    sold_count += 1

                except Exception as e:
                    print(f"  ✗ Failed to sell {currency}: {e}")

        print(f"\nBybit: Sold {sold_count} assets, skipped {skipped_count}")

    except Exception as e:
        print(f"Bybit error: {e}")
    finally:
        await exchange.close()


async def sell_all_assets():
    await sell_all_binance_async()
    await sell_all_bybit_async()

# ========================================
# MAIN EXECUTION
# ========================================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("EXCHANGE CLEANUP TOOL")
    print("=" * 50 + "\n")

    # Cancel all open orders
    cancel_binance_orders()
    cancel_bybit_orders()

    # Sell all assets to USDT
    asyncio.run(sell_all_assets())

    print("\n" + "=" * 50)
    print("CLEANUP COMPLETE")
    print("=" * 50 + "\n")