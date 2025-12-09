import ccxt.async_support as ccxt
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.error_mapping import map_exchange_errors

class BinanceConnector(ExchangeInterface):
    """
    Binance exchange connector implementing ExchangeInterface.
    """
    def __init__(self, api_key: str, secret_key: str, testnet: bool = False, default_type: str = "spot"):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'timeout': 60000,  # 60 seconds timeout
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

        return precision_rules

    @map_exchange_errors
    async def place_order(self, symbol: str, order_type: str, side: str, quantity: float, price: float = None, **kwargs):
        """
        Places an order on the exchange.
        """
        return await self.exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=quantity,
            price=price,
            params=kwargs
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
        Cancels an existing order by its ID.
        """
        return await self.exchange.cancel_order(order_id, symbol)

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
