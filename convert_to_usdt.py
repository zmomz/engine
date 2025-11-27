import ccxt.async_support as ccxt
import asyncio
from decimal import Decimal, ROUND_DOWN
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def convert_all_to_usdt(api_key: str, secret_key: str):
    exchange_id = 'binance'
    
    exchange = getattr(ccxt, exchange_id)({
        'apiKey': api_key,
        'secret': secret_key,
        'options': {
            'defaultType': 'spot',
        },
        'enableRateLimit': True, # Enable for smoother operations
    })
    exchange.set_sandbox_mode(True) # Ensure testnet is used

    try:
        logger.info("Loading markets...")
        markets = await exchange.load_markets()
        logger.info(f"Markets loaded. Found {len(markets)} symbols.")

        logger.info("Fetching balances...")
        balance = await exchange.fetch_balance()
        initial_usdt_free = Decimal(str(balance.get('USDT', {}).get('free', '0')))
        initial_usdt_used = Decimal(str(balance.get('USDT', {}).get('used', '0')))
        initial_usdt_total = Decimal(str(balance.get('USDT', {}).get('total', '0')))
        logger.info(f"Initial USDT balance - Free: {initial_usdt_free}, Used: {initial_usdt_used}, Total: {initial_usdt_total}")

        currencies_to_sell = []
        # Iterate through all assets that have a positive free balance to sell
        for currency, data in balance.get('free', {}).items():
            amount = Decimal(str(data))
            if currency != 'USDT' and amount > Decimal('0'):
                currencies_to_sell.append((currency, amount))

        if not currencies_to_sell:
            logger.info("No non-USDT assets with positive free balance to sell.")
            await exchange.close()
            return

        for currency, amount_to_sell in currencies_to_sell:
            symbol = f"{currency}/USDT"
            if symbol not in markets:
                logger.warning(f"Symbol {symbol} not found in markets. Skipping {currency}.")
                continue

            market = markets[symbol]
            min_qty = Decimal(str(market['limits']['amount']['min'] or '0'))
            min_notional = Decimal(str(market['limits']['cost']['min'] or '0'))
            price_precision = Decimal(str(market['precision']['price'] or '0.00000001')) # Default small precision
            amount_precision = Decimal(str(market['precision']['amount'] or '0.00000001'))

            logger.info(f"Processing {currency}. Available amount: {amount_to_sell} {currency}")
            logger.info(f"Market rules for {symbol}: min_qty={min_qty}, min_notional={min_notional}")

            try:
                # Fetch current ticker price to estimate notional value
                ticker = await exchange.fetch_ticker(symbol)
                current_price = Decimal(str(ticker['last']))
                
                # Round amount to sell to market precision
                amount_to_sell_rounded = (amount_to_sell / amount_precision).quantize(Decimal('1'), rounding=ROUND_DOWN) * amount_precision

                # Ensure amount meets minimum quantity
                if amount_to_sell_rounded < min_qty:
                    logger.info(f"Skipping {symbol}: Amount {amount_to_sell_rounded} {currency} is less than minimum quantity {min_qty}. ")
                    continue

                # Estimate notional value and ensure it meets minimum notional
                estimated_notional = amount_to_sell_rounded * current_price
                if estimated_notional < min_notional:
                    logger.info(f"Skipping {symbol}: Estimated notional {estimated_notional} USDT is less than minimum notional {min_notional} USDT. ")
                    continue
                
                logger.info(f"Placing market sell order for {amount_to_sell_rounded} {currency} on {symbol} (Estimated Notional: {estimated_notional} USDT)...")
                order = await exchange.create_market_sell_order(symbol, amount_to_sell_rounded)
                logger.info(f"Sold {currency}. Order ID: {order.get('id')}, Status: {order.get('status')}")
                await asyncio.sleep(exchange.rateLimit / 1000 + 0.1) # Respect rate limits

            except ccxt.InsufficientFunds as e:
                logger.warning(f"Insufficient funds to sell {currency}: {e}")
            except ccxt.InvalidOrder as e:
                logger.warning(f"Invalid order for {currency}: {e}")
            except ccxt.NetworkError as e:
                logger.error(f"Network error while selling {currency}: {e}")
            except ccxt.ExchangeError as e:
                logger.error(f"Exchange error while selling {currency}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while selling {currency}: {e}")

        logger.info("Refetching balances after conversion attempts...")
        final_balance = await exchange.fetch_balance()
        final_usdt_free = Decimal(str(final_balance.get('USDT', {}).get('free', '0')))
        logger.info(f"Final USDT free balance: {final_usdt_free}")

    except ccxt.AuthenticationError:
        logger.error("Authentication failed. Please check your API key and secret key for Binance Spot Testnet.")
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
    except Exception as e:
        logger.error(f"An unhandled error occurred in convert_all_to_usdt: {e}")
    finally:
        if exchange:
            await exchange.close()

if __name__ == "__main__":
    # These should be replaced with actual keys from users.json or environment variables
    BINANCE_TESTNET_API_KEY = "tB8ISxF1MaNEnOEZXu1GM1L8VNwYgOtDYmdmzLgclMeo4jrUwPC7NZWjQhelLoBU"
    BINANCE_TESTNET_SECRET_KEY = "CPjmcbTrdtixNet1c9c6AztJUVTNyuLSZ2Ba9cR88WVvfrBwdEXlL2VKtuhQjw5L"
    
    asyncio.run(convert_all_to_usdt(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_SECRET_KEY))