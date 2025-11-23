import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.exchange_abstraction.interface import ExchangeInterface
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository # New import
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.models.position_group import PositionGroup, PositionGroupStatus # New import
from app.exceptions import APIError, ExchangeConnectionError

logger = logging.getLogger(__name__)

class OrderService:
    """
    Service for managing the full lifecycle of DCA orders for a specific user.
    """
    def __init__(
        self, 
        session: AsyncSession,
        user: "User",
        exchange_connector: ExchangeInterface
    ):
        self.session = session
        self.user = user
        self.exchange_connector = exchange_connector
        self.dca_order_repository = DCAOrderRepository(self.session)
        self.position_group_repository = PositionGroupRepository(self.session) # New repository instance

    async def submit_order(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Submits a DCA order to the exchange and updates its status in the database.
        Includes retry logic with exponential backoff for transient network errors.
        """
        max_retries = 3
        base_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                # Ensure Enums are converted to their values and uppercase
                order_type_value = (dca_order.order_type.value if hasattr(dca_order.order_type, 'value') else str(dca_order.order_type)).upper()
                side_value = (dca_order.side.value if hasattr(dca_order.side, 'value') else str(dca_order.side)).upper()

                exchange_order_data = await self.exchange_connector.place_order(
                    symbol=dca_order.symbol,
                    order_type=order_type_value,
                    side=side_value,
                    quantity=dca_order.quantity,
                    price=dca_order.price
                )

                dca_order.exchange_order_id = exchange_order_data["id"]
                dca_order.status = OrderStatus.OPEN.value
                dca_order.submitted_at = datetime.utcnow()
                
                await self.dca_order_repository.update(dca_order)
                return dca_order
            except ExchangeConnectionError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt + 1} failed due to connection error. Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    dca_order.status = OrderStatus.FAILED.value
                    await self.dca_order_repository.update(dca_order)
                    raise APIError(f"Failed to submit order after {max_retries} attempts: {e}") from e
            except APIError as e:
                dca_order.status = OrderStatus.FAILED.value
                await self.dca_order_repository.update(dca_order)
                raise e
            except Exception as e:
                dca_order.status = OrderStatus.FAILED.value
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

            dca_order.status = OrderStatus.CANCELLED.value
            dca_order.cancelled_at = datetime.utcnow()
            
            await self.dca_order_repository.update(dca_order)
            return dca_order
        except APIError as e:
            dca_order.status = OrderStatus.FAILED.value
            await self.dca_order_repository.update(dca_order)
            raise e
        except Exception as e:
            dca_order.status = OrderStatus.FAILED.value
            await self.dca_order_repository.update(dca_order)
            raise APIError(f"Failed to cancel order: {e}") from e

    async def place_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Places a Take-Profit order for a filled DCA order.
        """
        if dca_order.status != OrderStatus.FILLED:
            raise APIError("Cannot place TP order for unfilled order.")
            
        if dca_order.tp_order_id:
             # TP order already exists
             return dca_order

        try:
            # Determine TP side
            tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"
            
            # Use the calculated tp_price from the order record
            tp_price = dca_order.tp_price
            
            # Place limit order for TP
            exchange_order_data = await self.exchange_connector.place_order(
                symbol=dca_order.symbol,
                order_type="LIMIT",
                side=tp_side,
                quantity=dca_order.filled_quantity,
                price=tp_price
            )
            
            dca_order.tp_order_id = exchange_order_data["id"]
            await self.dca_order_repository.update(dca_order)
            return dca_order
        except Exception as e:
             logger.error(f"Failed to place TP order for {dca_order.id}: {e}")
             # We don't raise here to avoid crashing the monitor loop, just log
             return dca_order

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
                new_status = OrderStatus.CANCELLED.value
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
            elif new_status == OrderStatus.CANCELLED.value and dca_order.cancelled_at is None:
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
        logger.info("OrderService: Starting reconciliation of open orders...")
        open_orders_in_db = await self.dca_order_repository.get_all_open_orders()
        
        for order in open_orders_in_db:
            try:
                await self.check_order_status(order)
                await self.session.commit() # Commit changes
                logger.info(f"OrderService: Reconciled order {order.id}. New status: {order.status}")
            except APIError as e:
                logger.error(f"OrderService: Failed to reconcile order {order.id}: {e}")
                # Log the error but continue with other orders
            except Exception as e:
                logger.error(f"OrderService: Unexpected error during reconciliation for order {order.id}: {e}")

    async def execute_force_close(self, group_id: uuid.UUID) -> PositionGroup:
        """
        Initiates the force-closing process for a given position group.
        Updates the position status to 'CLOSING'.
        """
        position_group = await self.position_group_repository.get(group_id)
        if not position_group:
            raise APIError(f"PositionGroup with ID {group_id} not found.", status_code=404)
        
        # Authorization check
        if position_group.user_id != self.user.id:
            raise APIError("Not authorized to close this position group.", status_code=403)

        if position_group.status == PositionGroupStatus.CLOSED.value:
            raise APIError(f"PositionGroup {group_id} is already closed.", status_code=400)

        position_group.status = PositionGroupStatus.CLOSING.value
        await self.position_group_repository.update(position_group)
        return position_group

    async def place_market_order(
        self,
        user_id: uuid.UUID,
        exchange: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        position_group_id: uuid.UUID = None
    ) -> Dict[str, Any]:
        """
        Places a market order directly on the exchange.
        Used for risk engine offsets and force closes.
        """
        try:
            # Ensure side is uppercase
            side_value = side.upper()
            
            exchange_order_data = await self.exchange_connector.place_order(
                symbol=symbol,
                order_type="MARKET",
                side=side_value,
                quantity=quantity,
                price=None # Market orders don't have a price
            )
            
            # TODO: Optionally record this as a distinct "MarketOrder" entity if needed for audit trails
            # For now, we just return the exchange data so the caller can log it.
            return exchange_order_data

        except APIError as e:
             raise e
        except Exception as e:
             raise APIError(f"Failed to place market order: {e}") from e

    async def cancel_open_orders_for_group(self, group_id: uuid.UUID):
        """
        Cancels all open and partially filled DCA orders for a specific position group.
        """
        orders = await self.dca_order_repository.get_open_orders_by_group_id(group_id)
        for order in orders:
            try:
                await self.cancel_order(order)
            except Exception as e:
                logger.error(f"Failed to cancel order {order.id} in group {group_id}: {e}")

    async def close_position_market(self, position_group: PositionGroup, quantity_to_close: Decimal):
        """
        Closes a position (or partial quantity) using a market order.
        Determines the correct side (opposite of position side) automatically.
        """
        close_side = "SELL" if position_group.side == "long" else "BUY"
        
        await self.place_market_order(
            user_id=position_group.user_id,
            exchange=position_group.exchange,
            symbol=position_group.symbol,
            side=close_side,
            quantity=quantity_to_close,
            position_group_id=position_group.id
        )

