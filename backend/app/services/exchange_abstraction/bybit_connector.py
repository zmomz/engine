import asyncio
import ccxt.async_support as ccxt
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.error_mapping import map_exchange_errors
import logging
from typing import List, Dict, Any, Optional # Added Optional

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
            'timeout': 60000,  # 60 seconds timeout
            'enableRateLimit': True,
            'asyncio_loop': None,  # Let ccxt manage its own event loop
            'verbose': True, # Enable verbose output for debugging
        })

        self.testnet_mode = testnet

        if testnet:
            self.exchange.set_sandbox_mode(True)
        
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
            
            precision_rules[symbol] = rules
            if market.get('id'):
                precision_rules[market['id']] = rules

        return precision_rules

    @map_exchange_errors
    async def place_order(self, symbol: str, order_type: str, side: str, quantity: float, price: float = None, **kwargs):
        """
        Places an order on the exchange.
        """

        try:
            logger.info(f"Placing order: symbol={symbol}, type={order_type}, side={side}, quantity={quantity}, price={price}, kwargs={kwargs}")

            params = kwargs.copy()
            if 'reduce_only' in kwargs:
                params['reduceOnly'] = kwargs['reduce_only']
                del params['reduce_only']

            result = await self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=quantity,
                price=price,
                params=params
            )

            # Extract native Bybit orderId from info field (CCXT returns composite ID)
            if 'info' in result and 'orderId' in result['info']:
                native_order_id = str(result['info']['orderId'])
                logger.info(f"Order placed successfully. CCXT ID: {result.get('id')}, Native Bybit ID: {native_order_id}")
                # Replace CCXT's composite ID with Bybit's native ID for consistency
                result['id'] = native_order_id
            else:
                logger.info(f"Order placed successfully: {result.get('id', 'unknown')}")

            # Small delay to allow background tasks to complete cleanly
            await asyncio.sleep(0.05)
            return result
        except ccxt.ExchangeError as e:
            # Check for error code 10005 (Invalid permissions/key) or 170131 (Insufficient balance)
            is_unified = self.exchange.options.get('accountType') == 'UNIFIED'
            error_msg = str(e)
            
            logger.error(f"Bybit place_order failed: {error_msg}")
            
            if ("10005" in error_msg or "170131" in error_msg) and is_unified:
                logger.warning(f"Bybit place_order failed with UNIFIED account type (Error: {error_msg}). Retrying with CONTRACT/SPOT fallback.")
                
                # Retry with CONTRACT (Derivatives/Futures)
                try:
                    logger.info(f"Retrying with CONTRACT account type...")
                    retry_params = {'accountType': 'CONTRACT'}
                    if 'reduce_only' in kwargs:
                        retry_params['reduceOnly'] = kwargs['reduce_only']
                        
                    result = await self.exchange.create_order(
                        symbol=symbol,
                        type=order_type,
                        side=side,
                        amount=quantity,
                        price=price,
                        params=retry_params
                    )
                    
                    # Extract native Bybit orderId
                    if 'info' in result and 'orderId' in result['info']:
                        native_order_id = str(result['info']['orderId'])
                        logger.info(f"Order placed successfully with CONTRACT. Native Bybit ID: {native_order_id}")
                        result['id'] = native_order_id
                    else:
                        logger.info(f"Order placed successfully with CONTRACT: {result.get('id', 'unknown')}")
                    return result
                except Exception as e2:
                    logger.warning(f"Bybit fallback to CONTRACT failed. Retrying with SPOT. Error: {e2}")
                    # Retry with SPOT
                    try:
                        retry_params_spot = {'accountType': 'SPOT'}
                        result = await self.exchange.create_order(
                            symbol=symbol,
                            type=order_type,
                            side=side,
                            amount=quantity,
                            price=price,
                            params=retry_params_spot
                        )
                        
                        # Extract native Bybit orderId
                        if 'info' in result and 'orderId' in result['info']:
                            native_order_id = str(result['info']['orderId'])
                            logger.info(f"Order placed successfully with SPOT. Native Bybit ID: {native_order_id}")
                            result['id'] = native_order_id
                        else:
                            logger.info(f"Order placed successfully with SPOT: {result.get('id', 'unknown')}")
                        return result
                    except Exception as e3:
                        logger.error(f"Bybit fallback to SPOT also failed. Error: {e3}")
                        raise e3 from e2
            else:
                raise e

    @map_exchange_errors
    async def get_order_status(self, order_id: str, symbol: str = None):
        """
        Fetches the status of a specific order by its ID.
        Returns the full order dictionary.
        Includes retry logic for Bybit conditional orders, account type fallback, and checks closed trades for quickly filled orders.
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
                
                # Try account type fallback if using UNIFIED
                is_unified = self.exchange.options.get('accountType') == 'UNIFIED'
                if is_unified:
                    logger.info(f"Attempting account type fallback for order {order_id} (SPOT/CONTRACT)...")
                    
                    # Try SPOT
                    try:
                        order = await self.exchange.fetch_order(order_id, symbol, params={'accountType': 'SPOT'})
                        logger.info(f"Order {order_id} found via SPOT account type.")
                        return order
                    except Exception as spot_e:
                        logger.warning(f"SPOT fallback failed for order {order_id}: {spot_e}")
                        
                        # Try CONTRACT
                        try:
                            order = await self.exchange.fetch_order(order_id, symbol, params={'accountType': 'CONTRACT'})
                            logger.info(f"Order {order_id} found via CONTRACT account type.")
                            return order
                        except Exception as contract_e:
                            logger.warning(f"CONTRACT fallback failed for order {order_id}: {contract_e}")
                
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
                    logger.warning(f"Order {order_id} not found via fetch_orders either.")
                    raise retry_e # If not found, re-raise the last exception
                except Exception as trade_e:
                    logger.error(f"Failed to fetch recent trades/orders for order {order_id}: {trade_e}")
                    raise retry_e # Re-raise original error

    @map_exchange_errors
    async def cancel_order(self, order_id: str, symbol: str = None):
        """
        Cancels an existing order by its ID with retry logic and status verification.
        Includes fallback for account types (UNIFIED -> SPOT -> CONTRACT).
        """
        max_retries = 3
        retry_delay = 0.5  # seconds

        for i in range(max_retries):
            try:
                # Attempt to cancel the order
                cancel_result = await self.exchange.cancel_order(order_id, symbol)
                logger.info(f"Order {order_id} cancelled successfully on attempt {i+1}.")
                return cancel_result
            except (ccxt.OrderNotFound, ccxt.ExchangeError) as e:
                # Check if we should fallback immediately
                if "10005" in str(e) and self.exchange.options.get('accountType') == 'UNIFIED':
                    logger.warning(f"Cancel failed with UNIFIED account error. Triggering fallback.")
                    break # Break to fallback block
                
                # If order not found, it might already be cancelled or filled. Verify status.
                logger.warning(f"Cancellation attempt {i+1} for order {order_id} failed: {e}. Verifying status...")
                await asyncio.sleep(retry_delay) # Wait before checking status and retrying

        # After max retries or break, explicitly check the order status
        try:
            order_status = await self.get_order_status(order_id, symbol)
            if order_status and order_status['status'] not in ['canceled', 'closed', 'filled']:
                 # If still active, try fallback if we haven't already
                 pass 
            else:
                logger.info(f"Order {order_id} is no longer active (status: {order_status['status']}). Considered successfully cancelled/closed.")
                return {'id': order_id, 'status': order_status['status']} # Return a success indicator
        except ccxt.OrderNotFound:
            logger.info(f"Order {order_id} not found after cancellation attempts. Assumed cancelled/closed.")
            return {'id': order_id, 'status': 'canceled'} # Assume successful cancellation due to not found
        except Exception:
            pass # Continue to fallback

        # Fallback Logic
        try:
            is_unified = self.exchange.options.get('accountType') == 'UNIFIED'
            if is_unified: 
                logger.info(f"Attempting cancel fallback for order {order_id} (SPOT/CONTRACT)...")
                
                # Try SPOT first (Prioritize Spot for Spot pairs)
                try:
                    return await self.exchange.cancel_order(order_id, symbol, params={'accountType': 'SPOT'})
                except Exception as e2:
                    # Try CONTRACT
                    try:
                        return await self.exchange.cancel_order(order_id, symbol, params={'accountType': 'CONTRACT'})
                    except Exception as e3:
                        logger.error(f"All cancel fallbacks failed for order {order_id}. Last error: {e3}")
                        raise OrderCancellationError(f"Failed to cancel order {order_id} on all account types.")
            else:
                 raise OrderCancellationError(f"Failed to cancel order {order_id} after retries.")
        except Exception as e:
             raise OrderCancellationError(f"Failed to cancel order {order_id}: {e}")

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
        Includes fallback for account types (UNIFIED -> SPOT -> CONTRACT).
        """
        try:
            balance = await self.exchange.fetch_balance(params={'accountType': 'UNIFIED'})
            return balance['total']
        except (ccxt.ExchangeError, Exception) as e:
            logger.warning(f"fetch_balance failed with UNIFIED: {e}. Retrying with SPOT/CONTRACT.")
            try:
                balance = await self.exchange.fetch_balance(params={'accountType': 'SPOT'})
                return balance['total']
            except Exception as e2:
                try:
                    balance = await self.exchange.fetch_balance(params={'accountType': 'CONTRACT'})
                    return balance['total']
                except Exception as e3:
                    logger.error(f"All fetch_balance fallbacks failed. Last error: {e3}")
                    raise e

    @map_exchange_errors
    async def fetch_free_balance(self):
        """
        Fetches the free (available) balance for all assets.
        Includes fallback for account types (UNIFIED -> SPOT -> CONTRACT).
        """
        try:
            balance = await self.exchange.fetch_balance(params={'accountType': 'UNIFIED'})
            return balance['free']
        except (ccxt.ExchangeError, Exception) as e:
            logger.warning(f"fetch_free_balance failed with UNIFIED: {e}. Retrying with SPOT/CONTRACT.")
            try:
                balance = await self.exchange.fetch_balance(params={'accountType': 'SPOT'})
                return balance['free']
            except Exception as e2:
                try:
                    balance = await self.exchange.fetch_balance(params={'accountType': 'CONTRACT'})
                    return balance['free']
                except Exception as e3:
                    logger.error(f"All fetch_free_balance fallbacks failed. Last error: {e3}")
                    raise e

    async def fetch_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        Fetches all currently open orders for a given symbol or all symbols on Bybit.
        Includes fallback for account types (UNIFIED -> SPOT -> CONTRACT).
        """
        try:
            return await self.exchange.fetch_open_orders(symbol, params={'accountType': 'UNIFIED'})
        except (ccxt.ExchangeError, Exception) as e:
            logger.warning(f"fetch_open_orders failed with UNIFIED: {e}. Retrying with SPOT/CONTRACT.")
            try:
                return await self.exchange.fetch_open_orders(symbol, params={'accountType': 'SPOT'})
            except Exception as e2:
                try:
                    return await self.exchange.fetch_open_orders(symbol, params={'accountType': 'CONTRACT'})
                except Exception as e3:
                    logger.error(f"All fetch_open_orders fallbacks failed. Last error: {e3}")
                    raise e

    async def close(self):
        """
        Closes the underlying ccxt exchange instance.
        """
        if self.exchange:
            await self.exchange.close()

    async def cancel_all_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        Cancels all open orders for a given symbol or all symbols on Bybit.
        Includes fallback for account types (UNIFIED -> SPOT -> CONTRACT).
        """
        if symbol:
            try:
                return await self.exchange.cancelAllOrders(symbol)
            except (ccxt.ExchangeError, Exception) as e:
                logger.warning(f"cancel_all_open_orders for symbol {symbol} failed with UNIFIED: {e}. Retrying with SPOT/CONTRACT.")
                try:
                    return await self.exchange.cancelAllOrders(symbol, params={'accountType': 'SPOT'})
                except Exception as e2:
                    try:
                        return await self.exchange.cancelAllOrders(symbol, params={'accountType': 'CONTRACT'})
                    except Exception as e3:
                        logger.error(f"All cancel_all_open_orders fallbacks failed for symbol {symbol}. Last error: {e3}")
                        raise e
        else:
            open_orders = await self.fetch_open_orders(symbol=None)
            cancelled_orders = []
            for order in open_orders:
                try:
                    cancelled_order = await self.exchange.cancel_order(order['id'], order['symbol'])
                    cancelled_orders.append(cancelled_order)
                except Exception as e:
                    # Log and continue if a single order cancellation fails
                    print(f"WARNING: Failed to cancel order {order['id']} ({order['symbol']}): {e}")
            return cancelled_orders

    

        

    