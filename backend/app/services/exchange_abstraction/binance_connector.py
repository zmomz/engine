import asyncio
import ccxt.async_support as ccxt
from typing import Literal
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.error_mapping import map_exchange_errors
from app.core.cache import get_cache
import logging

logger = logging.getLogger(__name__)


class OrderCancellationError(ccxt.NetworkError):
    """Raised when order cancellation fails after retries."""
    pass

class BinanceConnector(ExchangeInterface):
    """
    Binance exchange connector implementing ExchangeInterface.
    """
    def __init__(self, api_key: str, secret_key: str, testnet: bool = False, default_type: str = "spot"):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'timeout': 60000,  # 60 seconds timeout
            'enableRateLimit': True,
            'options': {
                'defaultType': default_type,
            },
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    @map_exchange_errors
    async def get_precision_rules(self):
        """
        Fetches market data to get precision rules for all symbols.
        Uses Redis cache with 24h TTL to avoid repeated expensive API calls.
        Returns a normalized dictionary:
        {
            "SYMBOL": {
                "tick_size": float,
                "step_size": float,
                "min_qty": float,
                "min_notional": float
            }
        }
        """
        # Try to get from cache first
        cache = await get_cache()
        cached_rules = await cache.get_precision_rules("binance")
        if cached_rules:
            logger.debug("Using cached precision rules for binance")
            return cached_rules

        logger.info("Fetching precision rules from Binance API (cache miss)")
        markets = await self.exchange.load_markets()
        precision_rules = {}

        for symbol, market in markets.items():
            # Normalize precision (handle decimal places vs float)
            # Binance via CCXT usually uses DECIMAL_PLACES (int) for precision
            # We need to convert to float step (e.g. 2 -> 0.01)

            price_precision = market['precision']['price']
            if isinstance(price_precision, int):
                tick_size = 1 / (10 ** price_precision)
            else:
                tick_size = price_precision

            amount_precision = market['precision']['amount']
            if isinstance(amount_precision, int):
                step_size = 1 / (10 ** amount_precision)
            else:
                step_size = amount_precision

            min_qty = market['limits']['amount']['min']
            min_notional = market['limits']['cost']['min']

            # Handle 'BTCUSDT' vs 'BTC/USDT' mapping if needed, but usually we use the unified symbol 'BTC/USDT'
            # The test uses "BTCUSDT" (TradingView format) so we might need to map or the caller handles it.
            # For now, we store by the key CCXT uses (BTC/USDT) AND the id (BTCUSDT) to be safe.

            rules = {
                "tick_size": tick_size,
                "step_size": step_size,
                "min_qty": min_qty,
                "min_notional": min_notional
            }

            precision_rules[symbol] = rules
            if market.get('id'):
                precision_rules[market['id']] = rules

        # Cache the results
        await cache.set_precision_rules("binance", precision_rules)
        logger.info(f"Cached precision rules for binance ({len(precision_rules)} symbols)")

        return precision_rules

    @map_exchange_errors
    async def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        price: float = None,
        amount_type: Literal["base", "quote"] = "base",
        **kwargs
    ):
        """
        Places an order on the exchange.
        Uses newOrderRespType='FULL' to get fee information in the response.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            order_type: "MARKET" or "LIMIT"
            side: "BUY" or "SELL"
            quantity: Amount to trade
            price: Price for limit orders
            amount_type: "base" for base currency, "quote" for quote currency
        """
        logger.info(f"Placing order: symbol={symbol}, type={order_type}, side={side}, "
                    f"quantity={quantity}, price={price}, amount_type={amount_type}")

        # Merge with FULL response type to get fee data
        params = {**kwargs, 'newOrderRespType': 'FULL'}

        is_market = order_type.upper() == 'MARKET'
        is_buy = side.upper() == 'BUY'

        if amount_type == "quote":
            if is_market:
                # For market orders with quote amount, use quoteOrderQty
                # Binance will spend exactly this amount of quote currency
                params['quoteOrderQty'] = quantity
                logger.info(f"Using quoteOrderQty={quantity} for market {side} order")
                return await self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=None,  # Let Binance calculate based on quoteOrderQty
                    price=None,
                    params=params
                )
            else:
                # For limit orders with quote amount, calculate base quantity
                if not price or price <= 0:
                    raise ValueError("Price required for limit orders with quote amount")
                base_quantity = quantity / price
                logger.info(f"Converting quote {quantity} to base {base_quantity} at price {price}")
                return await self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=base_quantity,
                    price=price,
                    params=params
                )
        else:
            # Base amount - pass directly
            return await self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=quantity,
                price=price if not is_market else None,  # Don't pass price for market orders
                params=params
            )

    @map_exchange_errors
    async def get_order_status(self, order_id: str, symbol: str = None):
        """
        Fetches the status of a specific order by its ID.
        Returns the full order dictionary.
        """
        order = await self.exchange.fetch_order(order_id, symbol)
        return order

    @map_exchange_errors
    async def cancel_order(self, order_id: str, symbol: str = None):
        """
        Cancels an existing order by its ID with retry logic and status verification.

        Args:
            order_id: The exchange order ID
            symbol: Trading pair symbol

        Returns:
            Cancel result dictionary with order status

        Raises:
            OrderCancellationError: If cancellation fails after retries
            ccxt.OrderNotFound: If order is not found on exchange
        """
        max_retries = 3
        retry_delay = 0.5  # seconds

        for i in range(max_retries):
            try:
                # Attempt to cancel the order
                cancel_result = await self.exchange.cancel_order(order_id, symbol)
                logger.info(f"Order {order_id} cancelled successfully on attempt {i+1}.")
                return cancel_result
            except ccxt.OrderNotFound:
                # Order not found - might already be cancelled or filled
                logger.warning(f"Order {order_id} not found during cancellation. Verifying status...")
                break  # Go to verification
            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                # Network or exchange issues - retry
                logger.warning(f"Cancellation attempt {i+1} for order {order_id} failed: {e}")
                if i < max_retries - 1:
                    await asyncio.sleep(retry_delay * (i + 1))  # Progressive delay
                continue

        # After retries, verify the order status
        try:
            order_status = await self.get_order_status(order_id, symbol)
            status = order_status.get('status', '').lower()

            if status in ['canceled', 'cancelled', 'closed', 'filled', 'expired']:
                logger.info(f"Order {order_id} is no longer active (status: {status}). "
                           "Considered successfully cancelled/closed.")
                return {'id': order_id, 'status': status}
            else:
                # Still active after all attempts
                raise OrderCancellationError(
                    f"Failed to cancel order {order_id} after {max_retries} attempts. "
                    f"Current status: {status}"
                )
        except ccxt.OrderNotFound:
            # Order not found after cancellation attempts - likely already cancelled
            logger.info(f"Order {order_id} not found after cancellation attempts. Assumed cancelled.")
            return {'id': order_id, 'status': 'canceled'}
        except OrderCancellationError:
            raise
        except Exception as e:
            raise OrderCancellationError(f"Failed to verify cancellation of order {order_id}: {e}")

    @map_exchange_errors
    async def get_current_price(self, symbol: str) -> float:
        """
        Fetches the last traded price for a symbol.
        """
        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker['last']

    @map_exchange_errors
    async def get_all_tickers(self):
        """
        Fetches all tickers from the exchange.
        """
        return await self.exchange.fetch_tickers()

    @map_exchange_errors
    async def fetch_balance(self):
        """
        Fetches the total balance for all assets.
        """
        balance = await self.exchange.fetch_balance()
        return balance['total']

    @map_exchange_errors
    async def fetch_free_balance(self):
        """
        Fetches the free (available) balance for all assets.
        """
        balance = await self.exchange.fetch_balance()
        return balance['free']

    async def close(self):
        """
        Closes the underlying ccxt exchange instance.
        """
        if self.exchange:
            await self.exchange.close()

    @map_exchange_errors
    async def get_trading_fee_rate(self, symbol: str = None) -> float:
        """
        Fetches the trading fee rate (taker fee) from Binance.
        Uses Redis cache with 1h TTL to avoid repeated API calls.
        Falls back to 0.001 (0.1%) if API call fails.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')

        Returns:
            Fee rate as decimal (e.g., 0.001 for 0.1%)
        """
        DEFAULT_FEE = 0.001  # 0.1% fallback

        try:
            # Try to get from cache first
            cache = await get_cache()
            cache_key = f"binance_fee_{symbol}" if symbol else "binance_fee_default"
            cached_fee = await cache.get(cache_key)
            if cached_fee is not None:
                return float(cached_fee)

            # Fetch from exchange
            if symbol:
                # Fetch fee for specific symbol
                fee_info = await self.exchange.fetch_trading_fee(symbol)
                taker_fee = fee_info.get('taker', DEFAULT_FEE)
            else:
                # Fetch account-level fees
                fees = await self.exchange.fetch_trading_fees()
                # Get first available or default
                if fees:
                    first_fee = next(iter(fees.values()), {})
                    taker_fee = first_fee.get('taker', DEFAULT_FEE)
                else:
                    taker_fee = DEFAULT_FEE

            # Cache for 1 hour
            await cache.set(cache_key, str(taker_fee), ttl=3600)
            logger.info(f"Fetched trading fee for {symbol or 'account'}: {taker_fee}")
            return float(taker_fee)

        except Exception as e:
            logger.warning(f"Failed to fetch trading fee from Binance: {e}. Using default {DEFAULT_FEE}")
            return DEFAULT_FEE
