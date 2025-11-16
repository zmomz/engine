import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
import uuid

from app.services.exchange_abstraction.interface import ExchangeInterface
from app.repositories.dca_order import DCAOrderRepository
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.exceptions import APIError, ExchangeConnectionError

class OrderService:
    """
    Service for managing the full lifecycle of DCA orders.
    """
    def __init__(
        self, 
        exchange_connector: ExchangeInterface, 
        dca_order_repository: DCAOrderRepository
    ):
        self.exchange_connector = exchange_connector
        self.dca_order_repository = dca_order_repository

    async def submit_order(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Submits a DCA order to the exchange and updates its status in the database.
        Includes retry logic with exponential backoff for transient network errors.
        """
        max_retries = 3
        base_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                exchange_order_data = await self.exchange_connector.place_order(
                    symbol=dca_order.symbol,
                    type=dca_order.order_type,
                    side=dca_order.side,
                    amount=dca_order.quantity,
                    price=dca_order.price
                )

                dca_order.exchange_order_id = exchange_order_data["id"]
                dca_order.status = OrderStatus.OPEN
                dca_order.submitted_at = datetime.utcnow()
                
                await self.dca_order_repository.update(dca_order)
                return dca_order
            except ExchangeConnectionError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"Attempt {attempt + 1} failed due to connection error. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    dca_order.status = OrderStatus.FAILED
                    await self.dca_order_repository.update(dca_order)
                    raise APIError(f"Failed to submit order after {max_retries} attempts: {e}") from e
            except APIError as e:
                dca_order.status = OrderStatus.FAILED
                await self.dca_order_repository.update(dca_order)
                raise e
            except Exception as e:
                dca_order.status = OrderStatus.FAILED
                await self.dca_order_repository.update(dca_order)
                raise APIError(f"Failed to submit order: {e}") from e

    async def cancel_order(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Cancels a DCA order on the exchange and updates its status in the database.
        """
        if not dca_order.exchange_order_id:
            raise APIError("Cannot cancel order without an exchange_order_id.")

        try:
            exchange_order_data = await self.exchange_connector.cancel_order(
                order_id=dca_order.exchange_order_id,
                symbol=dca_order.symbol
            )

            dca_order.status = OrderStatus.CANCELLED
            dca_order.cancelled_at = datetime.utcnow()
            
            await self.dca_order_repository.update(dca_order)
            return dca_order
        except APIError as e:
            dca_order.status = OrderStatus.FAILED
            await self.dca_order_repository.update(dca_order)
            raise e
        except Exception as e:
            dca_order.status = OrderStatus.FAILED
            await self.dca_order_repository.update(dca_order)
            raise APIError(f"Failed to cancel order: {e}") from e

    async def check_order_status(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Fetches the latest status of a DCA order from the exchange and updates the database.
        """
        if not dca_order.exchange_order_id:
            raise APIError("Cannot check status for order without an exchange_order_id.")

        try:
            exchange_order_data = await self.exchange_connector.get_order_status(
                order_id=dca_order.exchange_order_id,
                symbol=dca_order.symbol
            )

            exchange_status = exchange_order_data["status"]
            if exchange_status == "canceled":
                new_status = OrderStatus.CANCELLED
            else:
                new_status = OrderStatus(exchange_status)
            # Check if any relevant fields have changed before updating
            changed = False
            if dca_order.status != new_status:
                dca_order.status = new_status
                changed = True
            
            if new_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                filled_quantity_from_exchange = Decimal(str(exchange_order_data.get("filled", 0)))
                if dca_order.filled_quantity != filled_quantity_from_exchange:
                    dca_order.filled_quantity = filled_quantity_from_exchange
                    changed = True

                avg_fill_price_from_exchange = Decimal(str(exchange_order_data.get("price", 0))) # Assuming 'price' is avg_fill_price for filled orders
                if (dca_order.avg_fill_price is None and avg_fill_price_from_exchange != Decimal("0")) or \
                   (dca_order.avg_fill_price is not None and dca_order.avg_fill_price != avg_fill_price_from_exchange):
                    dca_order.avg_fill_price = avg_fill_price_from_exchange
                    changed = True

            if new_status == OrderStatus.FILLED and dca_order.filled_at is None:
                dca_order.filled_at = datetime.utcnow()
                changed = True
            elif new_status == OrderStatus.CANCELLED and dca_order.cancelled_at is None:
                dca_order.cancelled_at = datetime.utcnow()
                changed = True
            
            if changed:
                await self.dca_order_repository.update(dca_order)
            return dca_order
        except APIError as e:
            # Do not mark as FAILED here, as it might be a transient exchange error
            raise e
        except Exception as e:
            raise APIError(f"Failed to check order status: {e}") from e

    async def reconcile_open_orders(self):
        """
        Reconciles the status of open orders in the database with their actual status on the exchange.
        This is typically run on application startup to handle state drift.
        """
        print("OrderService: Starting reconciliation of open orders...")
        open_orders_in_db = await self.dca_order_repository.get_all_open_orders()
        
        for order in open_orders_in_db:
            try:
                await self.check_order_status(order)
                print(f"OrderService: Reconciled order {order.id}. New status: {order.status}")
            except APIError as e:
                print(f"OrderService: Failed to reconcile order {order.id}: {e}")
                # Log the error but continue with other orders
            except Exception as e:
                print(f"OrderService: Unexpected error during reconciliation for order {order.id}: {e}")
