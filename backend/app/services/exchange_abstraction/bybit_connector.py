import asyncio
import ccxt.async_support as ccxt
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.error_mapping import map_exchange_errors
import logging

logger = logging.getLogger(__name__)

class OrderCancellationError(ccxt.NetworkError):
    pass

class BybitConnector(ExchangeInterface):
    """
    Bybit exchange connector implementing ExchangeInterface.
    """
    def __init__(self, api_key: str, secret_key: str, testnet: bool = False, default_type: str = "spot", account_type: str = "UNIFIED"):

        logger.info(f"BybitConnector __init__ called:")
        logger.info(f"  - API Key: {api_key[:8]}")
        logger.info(f"  - Secret Key: {secret_key[:8]}")
        logger.info(f"  - Testnet: {testnet}")
        logger.info(f"  - Default Type: {default_type}")
        logger.info(f"  - Account Type: {account_type}")


        options = {
            'defaultType': default_type,
            'accountType': account_type,
        }
        
        # Add testnet option to ccxt options
        if testnet:
            options['testnet'] = True
        
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key,
            'options': options,
            'verbose': False, # Disable verbose output to reduce log noise
        })

        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': secret_key,
            'options': options,
            'verbose': False, # Disable verbose output to reduce log noise
        })
        self.testnet_mode = testnet

        self.testnet_mode = testnet

        if testnet:
            self.exchange.set_sandbox_mode(True)
        
        # Log the final state of testnet/sandbox mode after ccxt initialization

        logger.info(f"BybitConnector initialized: testnet={testnet}, account_type={account_type}, ccxt_testnet_mode={self.exchange.options.get('testnet')}, ccxt_default_type={self.exchange.options.get('defaultType')}")
        logger.info(f"CCXT Exchange Options: {self.exchange.options}")
        logger.info(f"CCXT Exchange URLs: {self.exchange.urls}")

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
            
        Returns the full order dictionary.
        Includes retry logic for Bybit conditional orders and checks closed trades for quickly filled orders.
        """
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            return order
        except ccxt.OrderNotFound as e:
            logger.warning(f"Order {order_id} not found via fetch_order, retrying with params={{'trigger': True}} for Bybit. Original error: {e}")
            try:
                order = await self.exchange.fetch_order(order_id, symbol, params={'trigger': True})
                return order
            except Exception as retry_e:
                logger.warning(f"Retry with trigger param for order {order_id} also failed: {retry_e}")
                
                # If still not found, check recent trades for the order ID
                logger.info(f"Attempting to find order {order_id} in recent trades for {symbol}...")
                try:
                    trades = await self.exchange.fetch_my_trades(symbol=symbol, limit=50)
                    for trade in trades:
                        # CCXT often links trades to their originating order ID
                        if trade.get('order') == order_id or trade.get('info').get('orderId') == order_id: # Bybit uses 'orderId' in info
                            logger.info(f"Order {order_id} found in recent trades. Status: {trade.get('status', 'filled')}")
                            # No implicit status reconstruction. Continue to fetch_orders fallback.
                    logger.warning(f"Order {order_id} not found in recent trades either.")
                    
                    # Fallback to fetch_orders (all orders) and filter
                    logger.info(f"Attempting to find order {order_id} via fetch_orders for {symbol}...")
                    all_orders = await self.exchange.fetch_orders(symbol=symbol, limit=50) # Fetch recent orders
                    for o in all_orders:
                        if o.get('id') == order_id or o.get('clientOrderId') == order_id or o.get('info', {}).get('orderId') == order_id:
                            logger.info(f"Order {order_id} found via fetch_orders. Status: {o.get('status', 'unknown')}")
                            return o # Return the full order object
        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker['last']

    @map_exchange_errors
    async def fetch_balance(self):
        """
        Fetches the total balance for all assets.
        """
        try:
            balance = await self.exchange.fetch_balance(params={'accountType': 'UNIFIED'})
        except ccxt.ExchangeError as e:
            # Handle Bybit Classic Account (non-Unified) attempting to access Unified endpoints
            if "accountType only support UNIFIED" in str(e):
                # Retry with CONTRACT account type (for Classic Futures)
                # Note: 'CONTRACT' is used for Derivatives Account in V5
                balance = await self.exchange.fetch_balance(params={'accountType': 'CONTRACT'})
            else:
                raise e
        
        return balance['total']

    @map_exchange_errors
    async def fetch_free_balance(self):
        """
        Fetches the free (available) balance for all assets.
        """
        try:
            balance = await self.exchange.fetch_balance(params={'accountType': 'UNIFIED'})
        except ccxt.ExchangeError as e:
            # Handle Bybit Classic Account (non-Unified) attempting to access Unified endpoints
            if "accountType only support UNIFIED" in str(e):
                # Retry with CONTRACT account type (for Classic Futures)
                # Note: 'CONTRACT' is used for Derivatives Account in V5
                balance = await self.exchange.fetch_balance(params={'accountType': 'CONTRACT'})
            else:
                raise e
        
        return balance['free']

    async def close(self):
        """
        Closes the underlying ccxt exchange instance.
        """
        if self.exchange:
            await self.exchange.close()