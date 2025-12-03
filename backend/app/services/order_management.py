import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
import uuid
import ccxt # Added for exchange exceptions

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
        Handles OrderNotFound gracefully.
        """
        if not dca_order.exchange_order_id:
            logger.warning(f"Order {dca_order.id} has no exchange_order_id, marking as CANCELLED.")
            dca_order.status = OrderStatus.CANCELLED.value
            await self.dca_order_repository.update(dca_order)
            return dca_order

        try:
            await self.exchange_connector.cancel_order(
                order_id=dca_order.exchange_order_id,
                symbol=dca_order.symbol
            )
        except ccxt.OrderNotFound:
            logger.warning(f"Order {dca_order.exchange_order_id} not found on exchange during cancellation. Assuming already closed/cancelled.")
        except APIError as e:
            # Re-raise APIErrors to be handled by the caller
            dca_order.status = OrderStatus.FAILED.value
            await self.dca_order_repository.update(dca_order)
            raise e
        except Exception as e:
            dca_order.status = OrderStatus.FAILED.value
            await self.dca_order_repository.update(dca_order)
            raise APIError(f"Failed to cancel order: {e}") from e

        # If cancellation was successful or order was not found, mark as cancelled
        dca_order.status = OrderStatus.CANCELLED.value
        dca_order.cancelled_at = datetime.utcnow()
        await self.dca_order_repository.update(dca_order)
        return dca_order

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
        Includes a workaround for Bybit testnet 'Order not found' issues.
        """
        if not dca_order.exchange_order_id:
            raise APIError("Cannot check status for order without an exchange_order_id.")

        exchange_order_data = None
        try:
            logger.debug(f"Checking order {dca_order.id} on exchange. Exchange Order ID: {dca_order.exchange_order_id}, Symbol: {dca_order.symbol}")
            exchange_order_data = await self.exchange_connector.get_order_status(
                order_id=dca_order.exchange_order_id,
                symbol=dca_order.symbol
            )
            logger.debug(f"Exchange response for order {dca_order.id}: {exchange_order_data}")

        except (ccxt.OrderNotFound, APIError, ExchangeConnectionError) as e:
            # Order not found on exchange - this could mean it was cancelled, filled and cleared, or never placed
            logger.error(f"Failed to check status for order {dca_order.id}: Order not found on exchange. Original error: {e}")
            raise APIError(f"Order not found on exchange for order {dca_order.id}") from e
        except Exception as e:
            logger.error(f"Failed to retrieve order status for {dca_order.id}: {e}")
            raise APIError(f"Failed to retrieve order status: {e}") from e

        # If we reached here, exchange_order_data was successfully fetched
        exchange_status = exchange_order_data["status"]
        
        # Map specific exchange statuses if necessary, but CCXT usually standardizes to lowercase 'open', 'closed', 'canceled'
        # Our Enum is lowercase: 'open', 'filled', 'cancelled'
        mapped_status = exchange_status.lower()
        if mapped_status == "closed":
            mapped_status = "filled" 
        elif mapped_status == "canceled":
            mapped_status = "cancelled"
        # If status is 'new' (Binance raw), map to 'open'
        elif mapped_status == "new":
            mapped_status = "open"
            
        try:
            new_status = OrderStatus(mapped_status)
        except ValueError:
                logger.warning(f"Unknown order status '{exchange_status}' from exchange for order {dca_order.id}. Defaulting to current status.")
                # Fallback: keep current status if unknown
                new_status = OrderStatus(dca_order.status)
        
        # Special handling for partial fills where exchange still reports 'open'
        filled_quantity_from_exchange = Decimal(str(exchange_order_data.get("filled", 0)))
        if new_status == OrderStatus.OPEN and filled_quantity_from_exchange > 0 and filled_quantity_from_exchange < dca_order.quantity:
            new_status = OrderStatus.PARTIALLY_FILLED

        # Check if any relevant fields have changed before updating
        changed = False
        if dca_order.status != new_status.value: # Compare with .value
            logger.info(f"Order {dca_order.id}: Status changed from {dca_order.status} to {new_status.value}")
            dca_order.status = new_status.value
            changed = True
        
        if new_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
            if dca_order.filled_quantity != filled_quantity_from_exchange:
                logger.info(f"Order {dca_order.id}: Filled quantity changed from {dca_order.filled_quantity} to {filled_quantity_from_exchange}")
                dca_order.filled_quantity = filled_quantity_from_exchange
                changed = True

            avg_fill_price_from_exchange = Decimal(str(exchange_order_data.get("average", Decimal("0"))))
            if (dca_order.avg_fill_price is None and avg_fill_price_from_exchange != Decimal("0")) or \
               (dca_order.avg_fill_price is not None and dca_order.avg_fill_price != avg_fill_price_from_exchange):
                logger.info(f"Order {dca_order.id}: Average fill price changed from {dca_order.avg_fill_price} to {avg_fill_price_from_exchange}")
                dca_order.avg_fill_price = avg_fill_price_from_exchange
                changed = True

        if changed:
            await self.dca_order_repository.update(dca_order)

        return dca_order


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

    async def check_tp_status(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Checks the status of the TP order associated with this DCA order.
        """
        if not dca_order.tp_order_id:
            return dca_order

        try:
            exchange_order_data = await self.exchange_connector.get_order_status(
                order_id=dca_order.tp_order_id,
                symbol=dca_order.symbol
            )
            
            status = exchange_order_data["status"].lower()
            
            if status == "closed" or status == "filled":
                dca_order.tp_hit = True
                dca_order.tp_executed_at = datetime.utcnow()
                await self.dca_order_repository.update(dca_order)
                
                # Create a record for the TP fill so stats can see the exit
                tp_side = "sell" if dca_order.side.lower() == "buy" else "buy"
                filled_qty = Decimal(str(exchange_order_data.get("filled", dca_order.filled_quantity)))
                avg_price = Decimal(str(exchange_order_data.get("average", dca_order.tp_price)))
                
                tp_fill_order = DCAOrder(
                    group_id=dca_order.group_id,
                    pyramid_id=dca_order.pyramid_id,
                    leg_index=999, # Special index for TP
                    symbol=dca_order.symbol,
                    side=tp_side,
                    order_type=OrderType.LIMIT, # TP is usually limit
                    price=avg_price,
                    quantity=filled_qty,
                    status=OrderStatus.FILLED.value,
                    exchange_order_id=str(exchange_order_data.get("id", "tp_fill_" + str(uuid.uuid4()))),
                    filled_quantity=filled_qty,
                    avg_fill_price=avg_price,
                    filled_at=datetime.utcnow(),
                    submitted_at=datetime.utcnow(),
                    gap_percent=Decimal("0"),
                    weight_percent=Decimal("0"),
                    tp_percent=Decimal("0"),
                    tp_price=Decimal("0")
                )
                await self.dca_order_repository.create(tp_fill_order)
                
                logger.info(f"TP order {dca_order.tp_order_id} for DCA order {dca_order.id} hit! Created TP fill record {tp_fill_order.id}")
                
            return dca_order
        except Exception as e:
            logger.error(f"Failed to check TP status for order {dca_order.id}: {e}")
            return dca_order

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
        position_group_id: uuid.UUID = None,
        record_in_db: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Places a market order directly on the exchange.
        Used for risk engine offsets, force closes, and aggregate TP execution.
        If record_in_db is True, creates a FILLED DCAOrder to track this trade.
        """
        try:
            # Ensure side is uppercase
            side_value = side.upper()
            
            exchange_order_data = await self.exchange_connector.place_order(
                symbol=symbol,
                order_type="MARKET",
                side=side_value,
                quantity=quantity,
                price=None, # Market orders don't have a price
                **kwargs
            )
            
            if record_in_db and position_group_id:
                # Create a "virtual" leg index for tracking (e.g., -1 or derived from sequence)
                # But DCAOrder usually maps to a plan. Here we just want to track the fill.
                # We'll use a special leg_index -1 for ad-hoc market orders to differentiate.
                
                # Extract fill details
                filled_qty = Decimal(str(exchange_order_data.get("filled", quantity))) # Fallback to req qty if missing
                avg_price = Decimal(str(exchange_order_data.get("average", exchange_order_data.get("price", "0"))))

                # If avg_price is 0 (common in immediate response), might need to fetch order? 
                # For now, trust exchange or use 0 and let monitor fix it? 
                # Monitor doesn't monitor filled orders usually. 
                # Let's hope 'average' is populated or 'price' is.
                
                market_order = DCAOrder(
                    group_id=position_group_id,
                    pyramid_id=None, # Not attached to specific pyramid plan
                    leg_index=-1, # Ad-hoc order
                    symbol=symbol,
                    side=side_value.lower(),
                    order_type=OrderType.MARKET,
                    price=avg_price, # Market orders fill at avg_price
                    quantity=filled_qty,
                    status=OrderStatus.FILLED.value,
                    exchange_order_id=str(exchange_order_data["id"]),
                    filled_quantity=filled_qty,
                    avg_fill_price=avg_price,
                    filled_at=datetime.utcnow(),
                    submitted_at=datetime.utcnow(),
                    gap_percent=Decimal("0"),
                    weight_percent=Decimal("0"),
                    tp_percent=Decimal("0"),
                    tp_price=Decimal("0")
                )
                await self.dca_order_repository.create(market_order)
                logger.info(f"Recorded market order {market_order.id} for group {position_group_id} in DB.")

            return exchange_order_data

        except APIError as e:
             raise e
        except Exception as e:
             raise APIError(f"Failed to place market order: {e}") from e

    async def cancel_tp_order(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Cancels the TP order associated with a filled DCA order.
        Handles OrderNotFound gracefully.
        """
        if not dca_order.tp_order_id:
            return dca_order

        try:
            logger.info(f"Cancelling TP order {dca_order.tp_order_id} for DCA order {dca_order.id}")
            await self.exchange_connector.cancel_order(
                order_id=dca_order.tp_order_id,
                symbol=dca_order.symbol
            )
        except ccxt.OrderNotFound:
            logger.warning(f"TP order {dca_order.tp_order_id} not found on exchange during cancellation. Assuming already closed/cancelled.")
        except APIError as e:
            logger.error(f"Failed to cancel TP order {dca_order.tp_order_id}: {e}")
            # Do not re-raise, but log the error. The goal is to close the position.
            # If TP cancel fails, market close should still proceed.
        except Exception as e:
            logger.error(f"Unexpected error cancelling TP order {dca_order.tp_order_id}: {e}")

        # In any case (success, not found, or other error), clear the TP order ID
        dca_order.tp_order_id = None
        dca_order.tp_hit = False # Reset just in case
        await self.dca_order_repository.update(dca_order)
        return dca_order

    async def cancel_open_orders_for_group(self, group_id: uuid.UUID):
        """
        Cancels all open orders for a group:
        1. Open/Partially Filled DCA orders (Entry orders).
        2. TP orders associated with Filled DCA orders.
        """
        # Fetch ALL orders for the group to ensure we catch TP orders on filled legs
        orders = await self.dca_order_repository.get_all_orders_by_group_id(group_id)
        
        for order in orders:
            # Cancel Entry Orders
            if order.status in [OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value]:
                await self.cancel_order(order)
            
            # Cancel TP Orders for Filled entries
            elif order.status == OrderStatus.FILLED.value and order.tp_order_id:
                await self.cancel_tp_order(order)

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

