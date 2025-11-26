#!/usr/bin/env python3
"""
Verifies Exchange API keys.

Usage:
    poetry run python scripts/verify_exchange_keys.py --exchange <EXCHANGE> --api-key <KEY> --secret-key <SECRET> [--testnet] [--passphrase <PASSPHRASE>]
"""
import asyncio
import argparse
import logging
import sys
import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPPORTED_EXCHANGES = ['binance', 'bybit', 'okx', 'kucoin']

async def test_keys(exchange_id, api_key, secret_key, passphrase, testnet):
    logger.info(f"Initializing {exchange_id} (Testnet: {testnet})...")
    
    exchange_class = getattr(ccxt, exchange_id)
    config = {
        'apiKey': api_key,
        'secret': secret_key,
    }
    
    if passphrase:
        config['password'] = passphrase
        
    exchange = exchange_class(config)
    
    if testnet:
        exchange.set_sandbox_mode(True)
    
    try:
        # Check markets first to ensure connectivity
        logger.info("Fetching markets...")
        await exchange.load_markets()
        logger.info(f"Markets loaded. Found {len(exchange.markets)} symbols.")

        # Check balance to verify permissions
        logger.info("Fetching balance...")
        balance = await exchange.fetch_balance()
        logger.info("SUCCESS: API keys are valid and have permission to fetch balance.")
        
        # Print a summary of non-zero balances
        if 'total' in balance:
            non_zero = {k: v for k, v in balance['total'].items() if v > 0}
            if non_zero:
                logger.info(f"Balances: {non_zero}")
            else:
                logger.info("Balance is empty (0 for all assets).")
                
    except ccxt.AuthenticationError:
        logger.error("FAILED: Authentication error. Check your API key, secret, and passphrase.")
        return False
    except ccxt.PermissionDenied:
        logger.error("FAILED: Permission denied. Check API key permissions.")
        return False
    except Exception as e:
        logger.error(f"FAILED: An unexpected error occurred: {e}")
        return False
    finally:
        await exchange.close()
    
    return True

async def run(args):
    return await test_keys(args.exchange, args.api_key, args.secret_key, args.passphrase, args.testnet)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exchange', required=True, choices=SUPPORTED_EXCHANGES, help='Exchange ID')
    parser.add_argument('--api-key', required=True, help='API Key')
    parser.add_argument('--secret-key', required=True, help='Secret Key')
    parser.add_argument('--passphrase', help='Passphrase (required for OKX, KuCoin, etc.)')
    parser.add_argument('--testnet', action='store_true', help='Use Testnet')
    
    args = parser.parse_args()
    
    try:
        success = asyncio.run(run(args))
        return 0 if success else 1
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
