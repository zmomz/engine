#!/usr/bin/env python3

"""
Cancel all open orders on Binance Spot Testnet
Requires: API key & Secret key

Testnet base URL: https://testnet.binance.vision
"""

import time
import hmac
import hashlib
import requests
import urllib.parse

# ===========================
# CONFIGURE YOUR API KEYS HERE
# ===========================
API_KEY = "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU"
API_SECRET = "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L".encode()

BASE_URL = "https://testnet.binance.vision"

# ---- Helper: Sign Parameters ----
def sign_params(params: dict):
    query = urllib.parse.urlencode(params)
    signature = hmac.new(API_SECRET, query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = signature
    return params

# ---- Helper: Send Signed Request ----
def signed_request(method, endpoint, params=None):
    if params is None:
        params = {}

    params["timestamp"] = int(time.time() * 1000)
    params = sign_params(params)

    headers = {"X-MBX-APIKEY": API_KEY}

    url = BASE_URL + endpoint
    if method == "GET":
        r = requests.get(url, headers=headers, params=params)
    elif method == "DELETE":
        r = requests.delete(url, headers=headers, params=params)
    else:
        raise ValueError("Unsupported HTTP method")

    if r.status_code != 200:
        print("Error:", r.text)
    return r.json()

# ---- Step 1: Fetch all trading symbols ----
def get_all_symbols():
    r = requests.get(BASE_URL + "/api/v3/exchangeInfo")
    data = r.json()
    symbols = [s["symbol"] for s in data["symbols"]]
    return symbols

# ---- Step 2: Cancel all open orders for each symbol ----
def cancel_all_orders():
    symbols = get_all_symbols()

    print(f"Total symbols found: {len(symbols)}")
    print("Checking for open orders...\n")

    for symbol in symbols:
        print(f"--- {symbol} ---")

        # Fetch open orders for this symbol
        open_orders = signed_request(
            "GET", "/api/v3/openOrders", {"symbol": symbol}
        )

        if not open_orders:
            print("No open orders")
            continue

        print(f"Found {len(open_orders)} open orders → Cancelling...")

        # Cancel all open orders
        result = signed_request(
            "DELETE", "/api/v3/openOrders", {"symbol": symbol}
        )

        print("Cancelled:", result)
        print()

# ---- Execute ----
if __name__ == "__main__":
    cancel_all_orders()
