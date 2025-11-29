import argparse
import asyncio
import ccxt.async_support as ccxt
import json
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def verify_exchange_universal(exchange_name: str, api_key: str, secret_key: str, testnet: bool, exchange_options: dict = None):
    logger.info(f"Attempting to verify {exchange_name} API key on testnet={testnet} with options={exchange_options or {}}...")

    results = []
    
    # Determine CCXT exchange class
    exchange_class = getattr(ccxt, exchange_name.lower(), None)
    if not exchange_class:
        logger.error(f"Unsupported exchange type: {exchange_name}")
        return [{"status": "error", "config": {}, "testnet": testnet, "error": f"Unsupported exchange type: {exchange_name}"}]

    # Configurations for various account types/settings for each exchange
    configs_to_try = []
    if exchange_name.lower() == "bybit":
        configs_to_try = [
            {"defaultType": "spot", "accountType": "UNIFIED"},
            {"defaultType": "future", "accountType": "UNIFIED"},
        ]
    elif exchange_name.lower() == "binance":
        configs_to_try = [
            {"defaultType": "spot"},
            {"defaultType": "future"},
        ]
    else:
        # For other exchanges, or if no specific options are required, try with empty options
        configs_to_try = [{}]
    
    # If specific options were passed, use them first/only
    if exchange_options:
        configs_to_try = [exchange_options]

    for options in configs_to_try:
        exchange = None
        try:
            ccxt_config = {
                'apiKey': api_key,
                'secret': secret_key,
                'options': options,
                'testnet': testnet, # Pass testnet directly
                'verbose': False, # Disable verbose output
            }
            exchange = exchange_class(ccxt_config)
            
            if testnet:
                exchange.set_sandbox_mode(True)

            # Attempt to fetch exchange time (a lightweight public endpoint)
            try:
                server_time = await exchange.fetch_time()
            except Exception as e:
                logger.error(f"Failed to fetch server time for {exchange_name} with options {options} and testnet={testnet}: {e}")
                results.append({"status": "connection_error", "config": options, "testnet": testnet, "error": str(e)})
                if exchange:
                    await exchange.close()
                continue # Try next combination if basic connectivity fails

            # Attempt to fetch balance
            balance = await exchange.fetch_balance()

            # --- Process Balance ---
            processed_balance = {"total": {}, "free": {}, "used": {}}
            for bal_type in ["total", "free", "used"]:
                if bal_type in balance and isinstance(balance[bal_type], dict):
                    for asset, amount in balance[bal_type].items():
                        try:
                            amount_float = float(amount) if amount is not None else 0.0
                            if amount_float > 0:
                                processed_balance[bal_type][asset] = amount_float
                        except (ValueError, TypeError):
                            logger.debug(f"Skipping asset {asset} due to non-numeric amount: {amount}")
                            pass

            # Calculate total_tvl in USDT (simplified for demonstration, proper conversion needs market prices)
            total_tvl_usdt = 0.0
            if "total" in balance and isinstance(balance["total"], dict):
                for asset, amount in balance["total"].items():
                    try:
                        amount_float = float(amount) if amount is not None else 0.0
                        if amount_float > 0:
                            if asset.upper() == "USDT": # Assuming USDT as base for TVL
                                total_tvl_usdt += amount_float
                            else:
                                try:
                                    ticker = await exchange.fetch_ticker(f"{asset}/USDT")
                                    if 'last' in ticker and ticker['last'] is not None:
                                        total_tvl_usdt += amount_float * float(ticker['last'])
                                    else:
                                        # logger.debug(f"Skipping TVL calculation for {asset}: No 'last' price in ticker for {asset}/USDT on {exchange_name}")
                                        pass # Suppress this debug log
                                except Exception as e:
                                    error_msg = str(e)
                                    if "does not have market symbol" in error_msg or "symbol not found" in error_msg.lower():
                                        # logger.debug(f"Skipping TVL calculation for {asset}: No market symbol {asset}/USDT on {exchange_name}")
                                        pass # Suppress this debug log
                                    else:
                                        logger.warning(f"Could not fetch price for {asset}/USDT on {exchange_name}: {e}")
                    except (ValueError, TypeError):
                        logger.debug(f"Skipping asset {asset} in TVL calculation due to non-numeric amount: {amount}")
                        pass
            
            # --- Infer API Key Type ---
            key_type_description = f"{exchange_name.capitalize()}"
            if options.get("accountType"):
                key_type_description += f" {options['accountType'].replace('UNIFIED', 'Unified').replace('CONTRACT', 'Contract').replace('SPOT', 'Spot')}"
            if options.get("defaultType"):
                key_type_description += f" {options['defaultType'].capitalize()}"
            if testnet:
                key_type_description += " Testnet"
            key_type_description += " API Key"

            # Only append to results, the main function will print the summary
            results.append({"status": "success", "config": options, "testnet": testnet, "balance": processed_balance, "total_tvl_usdt": total_tvl_usdt, "key_type": key_type_description})
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
