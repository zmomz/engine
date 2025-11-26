import argparse
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

def send_webhook(user_id, secret, base_url="http://localhost:8000"):
    url = f"{base_url}/api/v1/webhooks/{user_id}/tradingview"
    
    # Example payload matching the schema
    payload = {
        "user_id": user_id,
        "secret": secret, # Use the actual secret provided for validation
        "source": "tradingview",
        "timestamp": datetime.utcnow().isoformat(),
        "tv": {
            "exchange": "BINANCE",
            "symbol": "BTCUSDT",
            "timeframe": 15,
            "action": "long",
            "market_position": "long",
            "market_position_size": 1.0,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 50000.00,
            "close_price": 50000.00,
            "order_size": 1.0
        },
        "strategy_info": {
            "trade_id": f"trade_{int(time.time())}",
            "alert_name": "Manual Test Alert",
            "alert_message": "Testing webhook manually"
        },
        "execution_intent": {
            "type": "signal",
            "side": "buy",
            "position_size_type": "quote",
            "precision_mode": "auto"
        },
        "risk": {
            "stop_loss": 49000.00,
            "take_profit": 55000.00,
            "max_slippage_percent": 0.1
        }
    }

    payload_json = json.dumps(payload)
    
    headers = {
        "Content-Type": "application/json"
    }

    print(f"Sending webhook to: {url}")
    print(f"Payload: {payload_json}")

    req = urllib.request.Request(url, data=payload_json.encode('utf-8'), headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req) as response:
            print(f"Response Status: {response.status}")
            print(f"Response Body: {response.read().decode('utf-8')}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(f"Response Body: {e.read().decode('utf-8')}")
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
    except Exception as e:
        print(f"Error sending request: {e}")

if __name__ == "__main__":
    # Default values from your database (example user 'maaz')
    DEFAULT_USER_ID = "80e0a8a4-9468-43d1-a840-22d85ef5b413" 
    DEFAULT_SECRET = "41fb513d5ca1d1ae413c7f6e2395730d"

    parser = argparse.ArgumentParser(description="Trigger a test webhook.")
    parser.add_argument("--user_id", default=DEFAULT_USER_ID, help="User UUID")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help="Webhook Secret")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")

    args = parser.parse_args()
    send_webhook(args.user_id, args.secret, args.url)
