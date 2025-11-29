import argparse
import asyncio
import ccxt.async_support as ccxt
import json
import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def verify_bybit_key(api_key: str, secret_key: str, testnet: bool):
    logger.info(f"Attempting to verify Bybit API key on testnet={testnet}...")

    # Possible combinations for default_type and account_type
    bybit_options_combinations = [
        # Spot Trading
        {"defaultType": "spot", "accountType": "UNIFIED"},
        {"defaultType": "spot", "accountType": "CONTRACT"}, # Sometimes spot assets are in contract account in testnet
        {"defaultType": "spot", "accountType": "SPOT"}, # Explicit spot account type
        # Unified Margin / Derivatives
        {"defaultType": "future", "accountType": "UNIFIED"},
        {"defaultType": "future", "accountType": "CONTRACT"},
    ]

    results = []
    
    # Try with all combinations
    for options in bybit_options_combinations:
        logger.info(f"Trying Bybit with options: {options}, testnet: {testnet}")

        exchange = None
        try:
            bybit_config = {
                'apiKey': api_key,
                'secret': secret_key,
                'options': {
                    'defaultType': options.get('defaultType'),
                    'accountType': options.get('accountType'),
                },
                'testnet': testnet, # Pass testnet directly
                'verbose': True,
            }
            exchange = ccxt.bybit(bybit_config)
            
            if testnet:
                exchange.set_sandbox_mode(True)

            # Attempt to fetch exchange time (a lightweight public endpoint)
            try:
                server_time = await exchange.fetch_time()
                logger.info(f"Basic connectivity to Bybit established (server time: {server_time}) with options {options} and testnet={testnet}.")
            except Exception as e:
                logger.error(f"Failed to fetch server time for Bybit with options {options} and testnet={testnet}: {e}")
                results.append({"status": "connection_error", "config": options, "testnet": testnet, "error": str(e)})
                if exchange:
                    await exchange.close()
                return results # Return on failure to fetch server time

            # Attempt to fetch balance
            balance = await exchange.fetch_balance()
            logger.info(f"SUCCESS: Bybit connection established and balance fetched with options {options} and testnet={testnet}.")
            logger.info(f"Balance for Bybit: {json.dumps(balance, indent=2)}")
            results.append({"status": "success", "config": options, "testnet": testnet, "balance": balance})
            await exchange.close()
            return results # Return on first success
        except ccxt.NetworkError as e:
            logger.error(f"Network error with options {options} and testnet={testnet}: {e}")
            results.append({"status": "network_error", "config": options, "testnet": testnet, "error": str(e)})
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error with options {options} and testnet={testnet}: {e}")
            results.append({"status": "exchange_error", "config": options, "testnet": testnet, "error": str(e)})
        except Exception as e:
            logger.error(f"Unexpected error with options {options} and testnet={testnet}: {e}")
            results.append({"status": "unexpected_error", "config": options, "testnet": testnet, "error": str(e)})
        finally:
            if exchange:
                await exchange.close()
    return results

async def main():
    parser = argparse.ArgumentParser(description="Verify exchange API keys and test various configurations.")
    parser.add_argument("--exchange", type=str, required=True, help="The exchange to test (e.g., bybit, binance).")
    parser.add_argument("--api_key", type=str, required=True, help="The API key for the exchange.")
    parser.add_argument("--secret_key", type=str, required=True, help="The secret key for the exchange.")
    parser.add_argument("--testnet", type=bool, default=True, help="Whether to connect to testnet (default: True).")

    args = parser.parse_args()

    if args.exchange.lower() == "bybit":
        verification_results = await verify_bybit_key(args.api_key, args.secret_key, args.testnet)
        if verification_results:
            logger.info("\n--- Bybit Verification Summary ---")
            for result in verification_results:
                if result["status"] == "success":
                    logger.info(f"✅ SUCCESS for config: {result['config']}, testnet: {result['testnet']}")
                    logger.info(f"   Balance: {json.dumps(result['balance'], indent=2) if result.get('balance') else 'No balance retrieved.'}")
                elif result["status"] == "connection_error":
                    logger.error(f"❌ FAILED (Connection Error) for config: {result['config']}, testnet: {result['testnet']}, Error: {result['error']}")
                else:
                    logger.error(f"❌ FAILED for config: {result['config']}, testnet: {result['testnet']}, Error: {result['error']}")
        else:
            logger.info("No verification attempts were made for Bybit (unexpected).")

    # Add other exchanges here as elif blocks
    else:
        logger.error(f"Unsupported exchange: {args.exchange}")

if __name__ == "__main__":
    asyncio.run(main())