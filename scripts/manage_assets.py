#!/usr/bin/env python3

import asyncio
import json
import os
import sys

# Ensure the backend directory is in the Python path
script_dir = os.path.dirname(__file__)
backend_dir = os.path.abspath(os.path.join(script_dir, "..", "backend"))
sys.path.insert(0, backend_dir)

try:
    from app.services.exchange_abstraction.factory import get_exchange_connector
    from app.services.exchange_abstraction.interface import ExchangeInterface
    from ccxt import BaseExchange, InsufficientFunds, ExchangeError, InvalidOrder
except ImportError as e:
    print(f"Error: Could not import backend modules. Please ensure the backend is set up correctly and dependencies are installed. {{e}}", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
USER_ID = "b0270deb-c5d3-43ce-a5e6-c363fedb6ab1"  # User ID for maaz from users3.json
EXCHANGE_NAME = "binance"
QUOTE_CURRENCY = "USDT"

# File containing user data, including API keys
USER_DATA_FILE = "users3.json"

async def load_api_keys(user_id, exchange_name):
    """Loads API keys for a given user and exchange from the user data file."""
    try:
        with open(USER_DATA_FILE, 'r') as f:
            users_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: User data file '{{USER_DATA_FILE}}' not found.", file=sys.stderr)
        return None, None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{{USER_DATA_FILE}}'.", file=sys.stderr)
        return None, None

    for user in users_data:
        if user.get('id') == user_id:
            # Construct the key for the specific exchange, e.g., "Binance_testnet"
            # Assuming keys are directly under an exchange-named key like "Binance_testnet"
            exchange_key_name = f"{exchange_name.capitalize()}_testnet" # Adjust if it's not testnet or name differs
            if exchange_name == "binance": # Special handling for binance testnet as per users3.json
                exchange_key_name = "Binance_testnet"
                
            api_keys = user.get(exchange_key_name)
            if api_keys:
                api_key = api_keys.get('API_Key')
                secret_key = api_keys.get('Secret_Key')
                if api_key and secret_key:
                    print(f"Successfully loaded API keys for user {{user_id}} on {{exchange_name}}.")
                    return api_key, secret_key
                else:
                    print(f"Error: API_Key or Secret_Key missing for {{exchange_name}} in user {{user_id}} data.", file=sys.stderr)
                    return None, None
            else:
                print(f"Error: No keys found for '{{exchange_key_name}}' for user {{user_id}}.", file=sys.stderr)
                return None, None
    
    print(f"Error: User with ID '{{user_id}}' not found in '{{USER_DATA_FILE}}'.", file=sys.stderr)
    return None, None

def filter_balances(balances, quote_currency):
    """Filters balances to include only tradable assets (non-zero, not quote currency)."""
    tradable_assets = {}
    if not balances:
        return tradable_assets

    for asset, balance_info in balances.items():
        if asset == quote_currency or balance_info['free'] is None or balance_info['free'] == 0.0:
            continue
        tradable_assets[asset] = balance_info['free'] # Use free balance
    return tradable_assets

def get_symbol(asset, quote_currency):
    """Constructs the trading symbol (e.g., ETHUSDT)."""
    return f"{asset}{quote_currency}"

async def main():
    print(f"Starting asset management script for user: {{USER_ID}}, exchange: {{EXCHANGE_NAME}}, quote: {{QUOTE_CURRENCY}}")
    
    api_key, api_secret = await load_api_keys(USER_ID, EXCHANGE_NAME)
    if not api_key or not api_secret:
        sys.exit(1)

    connector: ExchangeInterface | None = None
    try:
        connector = await get_exchange_connector(
            user_id=USER_ID,
            api_key=api_key,
            api_secret=api_secret,
            exchange_name=EXCHANGE_NAME,
            quote_currency=QUOTE_CURRENCY
        )
        if not connector:
            print(f"Error: Could not create exchange connector for {{EXCHANGE_NAME}}.", file=sys.stderr)
            sys.exit(1)

        print("\n--- Fetching initial balances ---")
        initial_balances = await connector.fetch_balance()
        
        tradable_assets = filter_balances(initial_balances['free'], QUOTE_CURRENCY)

        if not tradable_assets:
            print("No tradable assets found (excluding quote currency).")
            return

        print(f"Found tradable assets: {{list(tradable_assets.keys())}}")

        # Fetch precision rules to ensure valid order sizes
        try:
            precision_rules = await connector.get_precision_rules()
            # print(f"Precision rules loaded: {precision_rules}") # For debugging
        except Exception as e:
            print(f"Error fetching precision rules: {{e}}", file=sys.stderr)
            # Proceeding without precision rules might lead to errors, but try anyway
            precision_rules = None

        print("\n--- Attempting to sell assets one by one ---")
        sold_assets = []
        for asset, quantity_to_sell in tradable_assets.items():
            symbol = get_symbol(asset, QUOTE_CURRENCY)
            print(f"\nAttempting to sell {{quantity_to_sell:.8f}} of {{asset}} (Symbol: {{symbol}})...")

            order_params = {
                "symbol": symbol,
                "side": "sell",
                "order_type": "market",
                "amount": quantity_to_sell,
                "params": {},
            }
            
            # Adjust order parameters based on precision rules if available
            if precision_rules and symbol in precision_rules:
                rules = precision_rules[symbol]
                # Adjust amount to meet minimums and precision
                min_amount = rules.get('min_amount')
                amount_precision = rules.get('amount_precision')
                
                if min_amount is not None and quantity_to_sell < min_amount:
                    print(f"  Skipping {{asset}}: Quantity {{quantity_to_sell:.8f}} is below minimum amount of {{min_amount:.8f}}.")
                    continue
                
                if amount_precision is not None:
                    # Round quantity to the correct precision
                    order_params["amount"] = round(quantity_to_sell, amount_precision)
                    if order_params["amount"] == 0.0: # If rounding makes it zero, skip
                        print(f"  Skipping {{asset}}: Rounded quantity {{order_params['amount']:.8f}} is zero after applying precision {{amount_precision}}.")
                        continue
                
                # Note: Notional value minimums are not directly handled by `place_order` amount, 
                # but can be checked from response or by pre-calculating if price is known.
                # For simplicity, we rely on the exchange to reject if notional is too low.

            try:
                # Execute the order
                order = await connector.place_order(**order_params)
                print(f"  Successfully placed sell order for {{asset}} ({{symbol}}): Order ID {{order['id']}}")
                sold_assets.append(asset)
                # Optional: Add a small delay to avoid hitting rate limits
                await asyncio.sleep(1)
            except InsufficientFunds:
                print(f"  FAILED to sell {{asset}}: Insufficient funds.", file=sys.stderr)
            except InvalidOrder as e:
                print(f"  FAILED to sell {{asset}} ({{symbol}}): Invalid order. {{e}}", file=sys.stderr)
            except ExchangeError as e:
                print(f"  FAILED to sell {{asset}} ({{symbol}}): Exchange error. {{e}}", file=sys.stderr)
            except Exception as e:
                print(f"  An unexpected error occurred while selling {{asset}} ({{symbol}}): {{e}}", file=sys.stderr)

        print("\n--- Fetching final balances ---")
        final_balances = await connector.fetch_balance()

        print("\n--- Final Balances ---")
        if final_balances and 'free' in final_balances:
            for asset, balance_info in final_balances['free'].items():
                if balance_info is not None and balance_info > 0.00000001: # Print only if balance is not negligible
                    print(f"  {{asset}}: {{balance_info:.8f}}")
        else:
            print("Could not retrieve final balances.")

    except Exception as e:
        print(f"An unexpected error occurred during script execution: {{e}}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Close the connector if it was initialized
        if connector:
            await connector.close()

if __name__ == "__main__":
    asyncio.run(main())
