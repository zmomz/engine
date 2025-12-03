#!/usr/bin/env python3

"""
Cancel all open orders and close positions on:
- Binance Spot Testnet
- Bybit (Unified Trading Account)
"""

import time
import hmac
import hashlib
import requests
import urllib.parse
import json

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

def sign_bybit_request(params: dict, timestamp: str):
    param_str = timestamp + BYBIT_API_KEY + "5000" + urllib.parse.urlencode(sorted(params.items()))
    signature = hmac.new(
        BYBIT_API_SECRET.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def bybit_request(method, endpoint, params=None):
    if params is None:
        params = {}
    
    timestamp = str(int(time.time() * 1000))
    signature = sign_bybit_request(params, timestamp)
    
    headers = {
        "X-BAPI-API-KEY": BYBIT_API_KEY,
        "X-BAPI-SIGN": signature,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": "5000",
        "Content-Type": "application/json"
    }
    
    url = BYBIT_BASE_URL + endpoint
    
    if method == "GET":
        r = requests.get(url, headers=headers, params=params)
    elif method == "POST":
        r = requests.post(url, headers=headers, json=params)
    else:
        raise ValueError("Unsupported HTTP method")
    
    if r.status_code != 200:
        print(f"Bybit Error: {r.status_code} - {r.text}")
        return None
    
    return r.json()

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
# MAIN EXECUTION
# ========================================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("EXCHANGE CLEANUP TOOL")
    print("=" * 50 + "\n")
    
    # Clean Binance
    cancel_binance_orders()
    
    # Clean Bybit
    cancel_bybit_orders()
    # Note: Spot trading doesn't have positions to close
    
    print("=" * 50)
    print("CLEANUP COMPLETE")
    print("=" * 50 + "\n")