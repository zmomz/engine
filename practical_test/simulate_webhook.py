#!/usr/bin/env python3
"""
Simulates a TradingView webhook signal by sending a valid JSON payload to the API.

Usage:
    python scripts/simulate_webhook.py --user-id UUID --secret SECRET --symbol BTCUSDT --side buy --type signal [options]
"""
import argparse
import json
import uuid
import datetime
import requests
import sys
import os

# Helper to generate current timestamp
def get_timestamp():
    return datetime.datetime.utcnow().isoformat() + "Z"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    
    # Connection args
    parser.add_argument('--url', default='http://localhost:8000', help='Base URL of the API')
    parser.add_argument('--user-id', required=True, help='Target User UUID')
    parser.add_argument('--secret', required=True, help='Webhook secret for the user')
    
    # TradingView Data args
    parser.add_argument('--exchange', default='BINANCE', help='Exchange name')
    parser.add_argument('--symbol', default='BTCUSDT', help='Trading symbol')
    parser.add_argument('--timeframe', type=int, default=1, help='Timeframe in minutes')
    parser.add_argument('--action', default='buy', help='Action (buy/sell)')
    parser.add_argument('--market-position', default='flat', help='Current market position')
    parser.add_argument('--market-position-size', type=float, default=0.0, help='Current position size')
    parser.add_argument('--entry-price', type=float, default=50000.0, help='Entry price')
    parser.add_argument('--close-price', type=float, default=50000.0, help='Close price')
    parser.add_argument('--order-size', type=float, default=0.0001, help='Order size')
    
    # Strategy Info
    parser.add_argument('--alert-name', default='Test Alert', help='Alert name')
    parser.add_argument('--trade-id', default='test_trade_1', help='Trade ID')
    
    # Execution Intent
    parser.add_argument('--type', choices=['signal', 'exit', 'reduce', 'reverse'], default='signal', help='Execution type')
    parser.add_argument('--side', choices=['buy', 'sell', 'long', 'short'], default='buy', help='Execution side')
    parser.add_argument('--pos-size-type', choices=['contracts', 'base', 'quote'], default='contracts', help='Position size type')
    
    # Risk
    parser.add_argument('--stop-loss', type=float, help='Stop loss price')
    parser.add_argument('--take-profit', type=float, help='Take profit price')
    
    args = parser.parse_args()
    
    # Construct Payload
    payload = {
        "user_id": args.user_id,
        "secret": args.secret,
        "source": "tradingview_sim",
        "timestamp": get_timestamp(),
        "tv": {
            "exchange": args.exchange,
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "action": args.action,
            "market_position": args.market_position,
            "market_position_size": args.market_position_size,
            "prev_market_position": "flat", # simplified
            "prev_market_position_size": 0.0, # simplified
            "entry_price": args.entry_price,
            "close_price": args.close_price,
            "order_size": args.order_size
        },
        "strategy_info": {
            "trade_id": args.trade_id,
            "alert_name": args.alert_name,
            "alert_message": "Simulation"
        },
        "execution_intent": {
            "type": args.type,
            "side": args.side,
            "position_size_type": args.pos_size_type,
            "precision_mode": "auto"
        },
        "risk": {
            "max_slippage_percent": 0.5
        }
    }
    
    if args.stop_loss:
        payload['risk']['stop_loss'] = args.stop_loss
    if args.take_profit:
        payload['risk']['take_profit'] = args.take_profit

    # Send Request
    endpoint = f"{args.url}/api/v1/webhooks/{args.user_id}/tradingview"
    
    print(f"Sending webhook to {endpoint}...")
    print("Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(endpoint, json=payload)
        print(f"\nResponse Status: {response.status_code}")
        try:
            print("Response Body:")
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
            
        if response.status_code == 202:
            print(f"\nstatus code: {response.status_code}.")
            return 0
        else:
            print(f"\nFAILED: Signal rejected.\nstatus code: {response.status_code}")
            return 1
            
    except requests.exceptions.ConnectionError:
        print(f"\nERROR: Could not connect to {args.url}. Is the server running?")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
