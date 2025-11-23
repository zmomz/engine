#!/usr/bin/env python3
"""
Verifies Binance API keys.

Usage:
    python scripts/verify_binance_keys.py --api-key <KEY> --secret-key <SECRET> [--testnet]
"""
import asyncio
import argparse
import logging
import sys
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_keys(api_key, secret_key, market_type, testnet):
    logger.info(f"Testing {market_type}...")
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'options': {
            'defaultType': market_type,
        },
    })
    if testnet:
        exchange.set_sandbox_mode(True)
    
    try:
        await exchange.fetch_balance()
        logger.info(f"SUCCESS: Fetched {market_type} balance.")
    except Exception as e:
        logger.error(f"FAILED: Could not fetch {market_type} balance. Error: {e}")
    finally:
        await exchange.close()

async def run(args):
    await test_keys(args.api_key, args.secret_key, 'future', args.testnet)
    await test_keys(args.api_key, args.secret_key, 'spot', args.testnet)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-key', required=True, help='Binance API Key')
    parser.add_argument('--secret-key', required=True, help='Binance Secret Key')
    parser.add_argument('--testnet', action='store_true', help='Use Testnet')
    
    args = parser.parse_args()
    
    try:
        asyncio.run(run(args))
        return 0
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
