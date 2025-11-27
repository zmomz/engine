import ccxt.async_support as ccxt
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.error_mapping import map_exchange_errors

class BybitConnector(ExchangeInterface):
    """
    Bybit exchange connector implementing ExchangeInterface.
    """
    def __init__(self, api_key: str, secret_key: str, testnet: bool = False):
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key,
            'options': {
                'defaultType': 'future',
            },
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)

    @map_exchange_errors
    async def get_precision_rules(self):
        """
        Fetches market data to get precision rules for all symbols.
        Returns a normalized dictionary.
        """
        markets = await self.exchange.load_markets()
        precision_rules = {}

        for symbol, market in markets.items():
            
            price_precision = market['precision']['price']
            if isinstance(price_precision, int):
                tick_size = 1 / (10 ** price_precision)
            else:
                tick_size = float(price_precision)

            amount_precision = market['precision']['amount']
            if isinstance(amount_precision, int):
                step_size = 1 / (10 ** amount_precision)
            else:
                step_size = float(amount_precision)

            min_qty = 0.001
            min_notional = 5.0
            
            if 'limits' in market:
                if 'amount' in market['limits'] and market['limits']['amount'].get('min'):
                     min_qty = float(market['limits']['amount']['min'])
                
                if 'cost' in market['limits'] and market['limits']['cost'].get('min'):
                     min_notional = float(market['limits']['cost']['min'])

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
    async def place_order(self, symbol: str, order_type: str, side: str, quantity: float, price: float = None):
        """
        Places an order on the exchange.
        """
        return await self.exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=quantity,
            price=price
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
    async def fetch_balance(self):
        """
        Fetches the total balance for all assets.
        """
        balance = await self.exchange.fetch_balance()
        return balance['total']
