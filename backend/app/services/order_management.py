import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid
import ccxt # Added for exchange exceptions

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.exchange_abstraction.interface import ExchangeInterface
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.exceptions import APIError, ExchangeConnectionError, SlippageExceededError


class CancellationStatus(Enum):
    """Status of order cancellation attempt."""
    SUCCESS = "success"                  # Order successfully cancelled
    ALREADY_CANCELLED = "already_cancelled"  # Order was already cancelled
    ALREADY_FILLED = "already_filled"    # Order was already filled
    NOT_FOUND = "not_found"              # Order not found on exchange
    FAILED = "failed"                    # Cancellation failed
    VERIFICATION_FAILED = "verification_failed"  # Could not verify cancellation


@dataclass
class CancellationResult:
    """Result of an order cancellation attempt with verification."""
    order_id: uuid.UUID
    exchange_order_id: Optional[str]
    status: CancellationStatus
    exchange_status: Optional[str] = None
    verified: bool = False
    error_message: Optional[str] = None
    attempts: int = 0

    @property
    def is_terminal(self) -> bool:
        """Check if the order is in a terminal state (no longer active)."""
        return self.status in [
            CancellationStatus.SUCCESS,
            CancellationStatus.ALREADY_CANCELLED,
            CancellationStatus.ALREADY_FILLED,
            CancellationStatus.NOT_FOUND
        ]


def round_to_tick_size(value: Decimal, tick_size: Decimal) -> Decimal:
    """Rounds a price value down to the nearest tick size."""
    return (value / tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick_size

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
        Includes retry logic with exponential backoff and jitter for transient network errors.

        For market orders with quote_amount set, uses quote-based ordering (spend exact USDT).
        For limit orders or orders without quote_amount, uses base-based ordering.

        Jitter is added to prevent thundering herd problem when multiple orders retry simultaneously.
        """
        max_retries = 3
        base_delay = 1  # seconds
        jitter_factor = 0.5  # Add up to 50% random jitter

        for attempt in range(max_retries):
            try:
                # Ensure Enums are converted to their values and uppercase
                order_type_value = (dca_order.order_type.value if hasattr(dca_order.order_type, 'value') else str(dca_order.order_type)).upper()
                side_value = (dca_order.side.value if hasattr(dca_order.side, 'value') else str(dca_order.side)).upper()

                # Determine amount_type based on order type and quote_amount availability
                # For market orders with quote_amount, use quote-based ordering
                is_market = order_type_value == "MARKET"
                has_quote_amount = dca_order.quote_amount is not None and dca_order.quote_amount > 0

                if is_market and has_quote_amount:
                    # Use quote amount directly for market orders
                    amount_type = "quote"
                    quantity_to_send = dca_order.quote_amount
                    logger.info(f"Submitting market order with quote amount: {quantity_to_send} USDT")
                else:
                    # Use base quantity for limit orders or when no quote_amount
                    amount_type = "base"
                    quantity_to_send = dca_order.quantity

                exchange_order_data = await self.exchange_connector.place_order(
                    symbol=dca_order.symbol,
                    order_type=order_type_value,
                    side=side_value,
                    quantity=quantity_to_send,
                    price=dca_order.price,
                    amount_type=amount_type
                )

                dca_order.exchange_order_id = exchange_order_data["id"]
                dca_order.status = OrderStatus.OPEN.value
                dca_order.submitted_at = datetime.utcnow()

                await self.dca_order_repository.update(dca_order)
                return dca_order
            except ExchangeConnectionError as e:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter to prevent thundering herd
                    base_wait = base_delay * (2 ** attempt)
                    jitter = random.uniform(0, base_wait * jitter_factor)
                    delay = base_wait + jitter
                    logger.warning(
                        f"Attempt {attempt + 1} failed due to connection error. "
                        f"Retrying in {delay:.2f}s (base: {base_wait}s, jitter: {jitter:.2f}s)..."
                    )
                    await asyncio.sleep(delay)
                else:
                    dca_order.status = OrderStatus.FAILED.value
                    await self.dca_order_repository.update(dca_order)
                    raise APIError(f"Failed to submit order after {max_retries} attempts: {e}") from e
            except APIError as e:
                # Check for precision-related errors and invalidate cache
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['precision', 'lot size', 'step size', 'tick size', 'quantity', 'notional', 'min_qty']):
                    logger.warning(f"Precision-related error detected, invalidating precision cache")
                    from app.core.cache import get_cache
                    cache = await get_cache()
                    # Extract exchange name from connector class name
                    exchange_name = self.exchange_connector.__class__.__name__.replace('Connector', '').lower()
                    await cache.invalidate_precision_rules(exchange_name)
                dca_order.status = OrderStatus.FAILED.value
                await self.dca_order_repository.update(dca_order)
                raise e
            except Exception as e:
                # Check for precision-related errors and invalidate cache
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['precision', 'lot size', 'step size', 'tick size', 'quantity', 'notional', 'min_qty']):
                    logger.warning(f"Precision-related error detected, invalidating precision cache")
                    from app.core.cache import get_cache
                    cache = await get_cache()
                    exchange_name = self.exchange_connector.__class__.__name__.replace('Connector', '').lower()
                    await cache.invalidate_precision_rules(exchange_name)
                dca_order.status = OrderStatus.FAILED.value
                await self.dca_order_repository.update(dca_order)
                raise APIError(f"Failed to submit order: {e}") from e

    async def cancel_order(self, dca_order: DCAOrder) -> DCAOrder:
        """
        Cancels a DCA order on the exchange and updates its status in the database.
        Uses cancel_order_verified internally for robust cancellation with verification.

        Args:
            dca_order: The order to cancel

        Returns:
            Updated DCAOrder with cancelled status

        Raises:
            APIError: If cancellation fails and order is still active
        """
        result = await self.cancel_order_verified(dca_order)

        if result.is_terminal:
            # Order is no longer active (cancelled, filled, or not found)
            if result.status == CancellationStatus.ALREADY_FILLED:
                # Don't change status if it was already filled
                logger.info(f"Order {dca_order.id} was already filled, not marking as cancelled")
            else:
                dca_order.status = OrderStatus.CANCELLED.value
                dca_order.cancelled_at = datetime.utcnow()
                await self.dca_order_repository.update(dca_order)
            return dca_order
        else:
            # Cancellation failed
            dca_order.status = OrderStatus.FAILED.value
            await self.dca_order_repository.update(dca_order)
            raise APIError(f"Failed to cancel order: {result.error_message}")

    async def cancel_order_verified(
        self,
        dca_order: DCAOrder,
        max_verification_attempts: int = 3,
        verification_delay: float = 0.5
    ) -> CancellationResult:
        """
        Cancels a DCA order with verification of the final state.

        This method provides detailed feedback about the cancellation attempt
        and verifies the order state on the exchange after cancellation.

        Args:
            dca_order: The order to cancel
            max_verification_attempts: Maximum attempts to verify cancellation
            verification_delay: Delay between verification attempts in seconds

        Returns:
            CancellationResult with detailed status information
        """
        if not dca_order.exchange_order_id:
            logger.warning(f"Order {dca_order.id} has no exchange_order_id, marking as CANCELLED.")
            return CancellationResult(
                order_id=dca_order.id,
                exchange_order_id=None,
                status=CancellationStatus.NOT_FOUND,
                verified=True,
                attempts=0
            )

        attempts = 0
        cancel_succeeded = False
        error_message = None

        # Step 1: Attempt cancellation
        try:
            await self.exchange_connector.cancel_order(
                order_id=dca_order.exchange_order_id,
                symbol=dca_order.symbol
            )
            cancel_succeeded = True
            logger.info(f"Cancel request sent for order {dca_order.exchange_order_id}")
        except ccxt.OrderNotFound:
            logger.warning(
                f"Order {dca_order.exchange_order_id} not found during cancellation. "
                "Will verify status."
            )
        except Exception as e:
            error_message = str(e)
            logger.error(f"Cancel request failed for order {dca_order.exchange_order_id}: {e}")

        # Step 2: Verify the order status on exchange
        for attempt in range(max_verification_attempts):
            attempts = attempt + 1
            try:
                await asyncio.sleep(verification_delay * (attempt + 1))  # Progressive delay

                order_status = await self.exchange_connector.get_order_status(
                    order_id=dca_order.exchange_order_id,
                    symbol=dca_order.symbol
                )

                exchange_status = order_status.get('status', '').lower()
                logger.debug(f"Verification attempt {attempts}: order {dca_order.exchange_order_id} status = {exchange_status}")

                # Check if order is in a terminal state
                if exchange_status in ['canceled', 'cancelled']:
                    return CancellationResult(
                        order_id=dca_order.id,
                        exchange_order_id=dca_order.exchange_order_id,
                        status=CancellationStatus.SUCCESS if cancel_succeeded else CancellationStatus.ALREADY_CANCELLED,
                        exchange_status=exchange_status,
                        verified=True,
                        attempts=attempts
                    )
                elif exchange_status in ['closed', 'filled']:
                    return CancellationResult(
                        order_id=dca_order.id,
                        exchange_order_id=dca_order.exchange_order_id,
                        status=CancellationStatus.ALREADY_FILLED,
                        exchange_status=exchange_status,
                        verified=True,
                        attempts=attempts
                    )
                elif exchange_status in ['expired', 'rejected']:
                    return CancellationResult(
                        order_id=dca_order.id,
                        exchange_order_id=dca_order.exchange_order_id,
                        status=CancellationStatus.ALREADY_CANCELLED,
                        exchange_status=exchange_status,
                        verified=True,
                        attempts=attempts
                    )
                # Order is still active, continue verification attempts

            except ccxt.OrderNotFound:
                # Order not found - likely already cancelled
                logger.info(f"Order {dca_order.exchange_order_id} not found during verification. Assuming cancelled.")
                return CancellationResult(
                    order_id=dca_order.id,
                    exchange_order_id=dca_order.exchange_order_id,
                    status=CancellationStatus.NOT_FOUND,
                    verified=True,
                    attempts=attempts
                )
            except Exception as e:
                logger.warning(f"Verification attempt {attempts} failed: {e}")
                if attempt == max_verification_attempts - 1:
                    error_message = f"Verification failed: {e}"

        # Verification exhausted without confirming terminal state
        if cancel_succeeded:
            # Cancel was sent but couldn't verify - assume success with warning
            logger.warning(
                f"Could not verify cancellation of order {dca_order.exchange_order_id} "
                f"after {attempts} attempts. Cancel request was accepted."
            )
            return CancellationResult(
                order_id=dca_order.id,
                exchange_order_id=dca_order.exchange_order_id,
                status=CancellationStatus.SUCCESS,
                verified=False,
                attempts=attempts,
                error_message="Cancellation sent but verification incomplete"
            )
        else:
            # Cancel failed and couldn't verify
            return CancellationResult(
                order_id=dca_order.id,
                exchange_order_id=dca_order.exchange_order_id,
                status=CancellationStatus.VERIFICATION_FAILED,
                verified=False,
                attempts=attempts,
                error_message=error_message or "Could not cancel or verify order status"
            )

    async def place_tp_order(
        self,
        dca_order: DCAOrder,
        adjust_for_fill_price: bool = True,
        tick_size: Optional[Decimal] = None
    ) -> DCAOrder:
        """
        Places a Take-Profit order for a filled DCA order.

        Args:
            dca_order: The filled DCA order to place TP for
            adjust_for_fill_price: If True, recalculates TP based on actual fill price
                                   rather than using the pre-calculated tp_price
            tick_size: Price tick size for rounding. If None, fetches from exchange.
        """
        if dca_order.status != OrderStatus.FILLED:
            raise APIError("Cannot place TP order for unfilled order.")

        if dca_order.tp_order_id:
            # TP order already exists
            return dca_order

        try:
            # Determine TP side
            tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"

            # Calculate TP price based on actual fill price if adjustment is enabled
            if adjust_for_fill_price and dca_order.avg_fill_price and dca_order.avg_fill_price > 0 and dca_order.tp_percent > 0:
                # Recalculate TP based on actual fill price
                if dca_order.side.upper() == "BUY":
                    adjusted_tp_price = dca_order.avg_fill_price * (Decimal("1") + dca_order.tp_percent / Decimal("100"))
                else:
                    adjusted_tp_price = dca_order.avg_fill_price * (Decimal("1") - dca_order.tp_percent / Decimal("100"))

                # Log if there's a difference between planned and adjusted TP
                if dca_order.tp_price and abs(adjusted_tp_price - dca_order.tp_price) > Decimal("0.0001"):
                    logger.info(
                        f"Adjusting TP for order {dca_order.id}: "
                        f"planned TP {dca_order.tp_price} -> adjusted TP {adjusted_tp_price} "
                        f"(fill price {dca_order.avg_fill_price} vs planned {dca_order.price})"
                    )
                tp_price = adjusted_tp_price
            else:
                # Use the pre-calculated tp_price from the order record
                tp_price = dca_order.tp_price

            # Round TP price to valid tick size
            if tick_size is None:
                # Fetch precision rules from exchange if not provided
                try:
                    precision_rules = await self.exchange_connector.get_precision_rules()
                    symbol_precision = precision_rules.get(dca_order.symbol, {})
                    tick_size = Decimal(str(symbol_precision.get("tick_size", "0.00000001")))
                except Exception as e:
                    logger.warning(f"Failed to fetch tick_size for {dca_order.symbol}, using default: {e}")
                    tick_size = Decimal("0.00000001")  # Safe fallback

            tp_price = round_to_tick_size(tp_price, tick_size)
            logger.debug(f"TP price rounded to tick_size {tick_size}: {tp_price}")

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

    async def place_tp_order_for_partial_fill(
        self,
        dca_order: DCAOrder,
        tick_size: Optional[Decimal] = None
    ) -> DCAOrder:
        """
        Places a Take-Profit order for a PARTIALLY FILLED DCA order.
        Uses the filled_quantity (not the full order quantity) for the TP.

        This allows users to secure profits on the portion that has filled
        while the rest of the order remains open.

        Args:
            dca_order: The partially filled DCA order
            tick_size: Price tick size for rounding. If None, fetches from exchange.
        """
        if dca_order.status != OrderStatus.PARTIALLY_FILLED:
            logger.warning(f"Order {dca_order.id} is not PARTIALLY_FILLED (status: {dca_order.status}), skipping partial TP")
            return dca_order

        if dca_order.tp_order_id:
            # TP order already exists for this partial fill
            return dca_order

        if not dca_order.filled_quantity or dca_order.filled_quantity <= 0:
            logger.warning(f"Order {dca_order.id} has no filled quantity, skipping partial TP")
            return dca_order

        try:
            # Determine TP side
            tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"

            # Calculate TP price based on actual fill price
            if dca_order.avg_fill_price and dca_order.avg_fill_price > 0 and dca_order.tp_percent > 0:
                if dca_order.side.upper() == "BUY":
                    tp_price = dca_order.avg_fill_price * (Decimal("1") + dca_order.tp_percent / Decimal("100"))
                else:
                    tp_price = dca_order.avg_fill_price * (Decimal("1") - dca_order.tp_percent / Decimal("100"))
            else:
                tp_price = dca_order.tp_price

            # Round TP price to valid tick size
            if tick_size is None:
                try:
                    precision_rules = await self.exchange_connector.get_precision_rules()
                    symbol_precision = precision_rules.get(dca_order.symbol, {})
                    tick_size = Decimal(str(symbol_precision.get("tick_size", "0.00000001")))
                except Exception as e:
                    logger.warning(f"Failed to fetch tick_size for {dca_order.symbol}, using default: {e}")
                    tick_size = Decimal("0.00000001")

            tp_price = round_to_tick_size(tp_price, tick_size)

            logger.info(
                f"Placing partial TP for order {dca_order.id}: "
                f"filled_qty={dca_order.filled_quantity}, tp_price={tp_price}"
            )

            # Place limit order for partial TP
            exchange_order_data = await self.exchange_connector.place_order(
                symbol=dca_order.symbol,
                order_type="LIMIT",
                side=tp_side,
                quantity=dca_order.filled_quantity,  # Use filled quantity, not full order qty
                price=tp_price
            )

            dca_order.tp_order_id = exchange_order_data["id"]
            await self.dca_order_repository.update(dca_order)

            logger.info(f"Partial TP order placed for {dca_order.id}: {exchange_order_data['id']}")
            return dca_order

        except Exception as e:
            logger.error(f"Failed to place partial TP order for {dca_order.id}: {e}")
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
        logger.info(f"Order {dca_order.id}: Current DB status='{dca_order.status}', Exchange status='{new_status.value}', filled_qty={filled_quantity_from_exchange}")
        if dca_order.status != new_status.value: # Compare with .value
            logger.info(f"Order {dca_order.id}: Status CHANGING from '{dca_order.status}' to '{new_status.value}'")
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

            # Extract and store fee data from exchange response
            # CCXT returns fee as object: {"cost": 0.001, "currency": "USDT", "rate": 0.0001}
            # Mock exchange returns fee as number directly
            raw_fee = exchange_order_data.get("fee", 0)
            if isinstance(raw_fee, dict):
                # CCXT unified format (Binance, Bybit, etc.)
                fee_from_exchange = Decimal(str(raw_fee.get("cost", 0) or 0))
                fee_currency = raw_fee.get("currency")

                # Extract base currency from symbol (e.g., "BTC" from "BTC/USDT" or "BTCUSDT")
                symbol_str = dca_order.symbol
                if "/" in symbol_str:
                    base_currency = symbol_str.split("/")[0].upper()
                else:
                    # Handle symbols without slash (e.g., BTCUSDT)
                    # Common quote currencies to strip
                    for quote in ["USDT", "BUSD", "USDC", "USD", "TUSD", "DAI"]:
                        if symbol_str.upper().endswith(quote):
                            base_currency = symbol_str.upper()[:-len(quote)]
                            break
                    else:
                        base_currency = symbol_str[:3].upper()  # Fallback: first 3 chars

                # Bybit fix: CCXT may misreport fee currency. Check raw info.cumFeeDetail
                # Bybit returns: {'cumFeeDetail': {'BTC': '0.000009'}} for base currency fees
                info = exchange_order_data.get("info", {})
                cum_fee_detail = info.get("cumFeeDetail", {})
                if cum_fee_detail and isinstance(cum_fee_detail, dict):
                    # Get the actual fee currency from Bybit's raw response
                    for actual_currency, actual_fee_amount in cum_fee_detail.items():
                        if actual_fee_amount and Decimal(str(actual_fee_amount)) > 0:
                            # Store fee in original currency (base or quote)
                            fee_from_exchange = Decimal(str(actual_fee_amount))
                            fee_currency = actual_currency
                            break

                # Only deduct fee from filled_quantity if fee is in BASE currency
                # This handles: Bybit (fees in BTC), but NOT Binance with BNB discount (fees in BNB)
                if fee_currency and fee_currency.upper() == base_currency:
                    # Fee is in base currency - deduct from filled_quantity
                    # This ensures we track the actual receivable amount
                    if filled_quantity_from_exchange and filled_quantity_from_exchange > fee_from_exchange:
                        adjusted_qty = filled_quantity_from_exchange - fee_from_exchange
                        logger.info(f"Order {dca_order.id}: Fee {fee_from_exchange} {fee_currency} deducted from filled qty. Adjusted: {filled_quantity_from_exchange} -> {adjusted_qty}")
                        filled_quantity_from_exchange = adjusted_qty
                        # Save the adjusted quantity to the order
                        dca_order.filled_quantity = adjusted_qty
                        changed = True
            else:
                # Mock exchange or direct number format
                fee_from_exchange = Decimal(str(raw_fee or 0))
                fee_currency = exchange_order_data.get("fee_currency")
            if fee_from_exchange > 0 and (dca_order.fee is None or dca_order.fee != fee_from_exchange):
                logger.info(f"Order {dca_order.id}: Fee updated to {fee_from_exchange} {fee_currency}")
                dca_order.fee = fee_from_exchange
                dca_order.fee_currency = fee_currency
                changed = True
            elif fee_from_exchange <= 0 and new_status == OrderStatus.FILLED:
                # Exchange didn't return fee - estimate it for realistic PnL tracking
                # This is common on testnets that don't report fees
                try:
                    filled_qty = Decimal(str(filled_quantity_from_exchange or 0))
                    avg_price = avg_fill_price_from_exchange if avg_fill_price_from_exchange > 0 else dca_order.price

                    if filled_qty > 0 and avg_price and avg_price > 0:
                        # Get dynamic fee rate from exchange (cached, fallback 0.1%)
                        fee_rate = Decimal(str(
                            await self.exchange_connector.get_trading_fee_rate(dca_order.symbol)
                        ))

                        # Estimate: trade_value × fee_rate
                        trade_value = filled_qty * avg_price
                        estimated_fee = trade_value * fee_rate

                        if dca_order.fee is None or dca_order.fee == Decimal("0"):
                            dca_order.fee = estimated_fee
                            dca_order.fee_currency = "USDT"  # Assume quote currency for estimates
                            logger.info(f"Order {dca_order.id}: Fee estimated at {estimated_fee} USDT (rate: {fee_rate})")
                            changed = True
                    else:
                        logger.warning(
                            f"Order {dca_order.id} ({dca_order.symbol}): Cannot estimate fee - "
                            f"filled_qty={filled_qty}, avg_price={avg_price}. Exchange returned no fee."
                        )
                except Exception as e:
                    logger.warning(f"Order {dca_order.id} ({dca_order.symbol}): Failed to estimate fee: {e}")

            # Set filled_at if the order is now filled and it wasn't before
            if new_status == OrderStatus.FILLED and dca_order.filled_at is None:
                dca_order.filled_at = datetime.utcnow()
                changed = True

        if changed:
            logger.info(f"Order {dca_order.id}: Saving changes to database (status={dca_order.status})")
            await self.dca_order_repository.update(dca_order)
            logger.info(f"Order {dca_order.id}: Repository update completed")
        else:
            logger.info(f"Order {dca_order.id}: No changes detected, skipping update")

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

    async def check_and_retry_stale_tp(
        self,
        dca_order: DCAOrder,
        stale_threshold_hours: float = 24.0,
        use_market_fallback: bool = True
    ) -> DCAOrder:
        """
        Check if a TP order is stale (unfilled for too long) and retry.

        If the TP has been open for longer than stale_threshold_hours,
        cancels it and either:
        1. Places a new limit order at current market price + TP%, or
        2. Places a market order if use_market_fallback is True

        Args:
            dca_order: The DCA order with TP to check
            stale_threshold_hours: Hours after which TP is considered stale
            use_market_fallback: If True, use market order for stale TPs

        Returns:
            Updated DCA order
        """
        if not dca_order.tp_order_id or dca_order.tp_hit:
            return dca_order

        # Check how long the TP has been open
        if not dca_order.filled_at:
            return dca_order

        hours_since_fill = (datetime.utcnow() - dca_order.filled_at).total_seconds() / 3600

        if hours_since_fill < stale_threshold_hours:
            return dca_order

        logger.info(
            f"TP order {dca_order.tp_order_id} for {dca_order.symbol} is stale "
            f"({hours_since_fill:.1f} hours). Attempting retry..."
        )

        try:
            # First check if the TP is still open on exchange
            exchange_order_data = await self.exchange_connector.get_order_status(
                order_id=dca_order.tp_order_id,
                symbol=dca_order.symbol
            )

            status = exchange_order_data["status"].lower()

            # If already filled, just update and return
            if status in ["closed", "filled"]:
                dca_order.tp_hit = True
                dca_order.tp_executed_at = datetime.utcnow()
                await self.dca_order_repository.update(dca_order)
                return dca_order

            # If still open, cancel and retry
            if status == "open":
                logger.info(f"Cancelling stale TP order {dca_order.tp_order_id}")

                try:
                    await self.exchange_connector.cancel_order(
                        order_id=dca_order.tp_order_id,
                        symbol=dca_order.symbol
                    )
                except Exception as cancel_error:
                    logger.warning(f"Failed to cancel stale TP: {cancel_error}")
                    return dca_order

                # Clear the old TP order ID
                old_tp_order_id = dca_order.tp_order_id
                dca_order.tp_order_id = None
                await self.dca_order_repository.update(dca_order)

                if use_market_fallback:
                    # Use market order for guaranteed execution
                    logger.info(f"Placing market order fallback for stale TP on {dca_order.symbol}")

                    tp_side = "SELL" if dca_order.side.upper() == "BUY" else "BUY"

                    try:
                        market_result = await self.exchange_connector.place_order(
                            symbol=dca_order.symbol,
                            order_type="MARKET",
                            side=tp_side,
                            quantity=dca_order.filled_quantity
                        )

                        dca_order.tp_order_id = market_result["id"]
                        dca_order.tp_hit = True
                        dca_order.tp_executed_at = datetime.utcnow()
                        await self.dca_order_repository.update(dca_order)

                        logger.info(
                            f"Market fallback executed for stale TP. "
                            f"Old order: {old_tp_order_id}, New order: {market_result['id']}"
                        )
                    except Exception as market_error:
                        logger.error(f"Market fallback failed for stale TP: {market_error}")
                else:
                    # Place new limit order at better price
                    logger.info(f"Placing new limit TP for {dca_order.symbol}")
                    await self.place_tp_order(dca_order, adjust_for_fill_price=True)

            return dca_order

        except Exception as e:
            logger.error(f"Failed to handle stale TP for order {dca_order.id}: {e}")
            return dca_order

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
        expected_price: Decimal = None,
        max_slippage_percent: float = None,
        slippage_action: str = "warn",
        pre_check_slippage: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Places a market order directly on the exchange.
        Used for risk engine offsets, force closes, and aggregate TP execution.
        If record_in_db is True, creates a FILLED DCAOrder to track this trade.

        Args:
            expected_price: Expected execution price for slippage calculation
            max_slippage_percent: Maximum allowed slippage percentage (e.g., 1.0 = 1%)
            slippage_action: What to do when slippage exceeds threshold:
                - "warn": Log warning only (default, backward compatible)
                - "reject": Raise SlippageExceededError (order still executed for post-check, rejected for pre-check)
            pre_check_slippage: If True, checks slippage against current price BEFORE execution (default True)
        """
        try:
            # Extract pyramid_id from kwargs before passing to exchange
            pyramid_id = kwargs.pop('pyramid_id', None)

            # Ensure side is uppercase
            side_value = side.upper()

            # Pre-execution slippage check
            if pre_check_slippage and expected_price and max_slippage_percent is not None:
                try:
                    current_price = Decimal(str(await self.exchange_connector.get_current_price(symbol)))

                    if current_price > 0:
                        # Estimate slippage based on current price
                        if side_value == "BUY":
                            # For buys, slippage is positive when current price > expected
                            estimated_slippage = float((current_price - expected_price) / expected_price * 100)
                        else:
                            # For sells, slippage is positive when current price < expected
                            estimated_slippage = float((expected_price - current_price) / expected_price * 100)

                        if estimated_slippage > max_slippage_percent:
                            slippage_msg = (
                                f"Pre-execution slippage check failed for {symbol} {side_value}: "
                                f"expected {expected_price}, current {current_price}, "
                                f"estimated slippage {estimated_slippage:.2f}% > max {max_slippage_percent}%"
                            )

                            if slippage_action == "reject":
                                logger.error(slippage_msg)
                                raise SlippageExceededError(slippage_msg)
                            else:
                                logger.warning(slippage_msg + " - proceeding with order")
                except SlippageExceededError:
                    raise  # Re-raise slippage error
                except Exception as e:
                    # Don't fail the order if pre-check fails - log and continue
                    logger.warning(f"Pre-execution slippage check failed for {symbol}: {e} - proceeding with order")

            exchange_order_data = await self.exchange_connector.place_order(
                symbol=symbol,
                order_type="MARKET",
                side=side_value,
                quantity=quantity,
                price=None, # Market orders don't have a price
                **kwargs
            )

            # Slippage protection check (post-execution)
            slippage_exceeded = False
            actual_slippage_percent = 0.0
            avg_price = Decimal("0")

            if expected_price and max_slippage_percent is not None:
                avg_price_raw = exchange_order_data.get("average") or exchange_order_data.get("avg_price") or exchange_order_data.get("price") or "0"
                avg_price = Decimal(str(avg_price_raw)) if avg_price_raw else Decimal("0")
                if avg_price > 0:
                    # Calculate actual slippage
                    if side_value == "BUY":
                        # For buys, slippage is positive when fill price > expected
                        actual_slippage_percent = float((avg_price - expected_price) / expected_price * 100)
                    else:
                        # For sells, slippage is positive when fill price < expected
                        actual_slippage_percent = float((expected_price - avg_price) / expected_price * 100)

                    if actual_slippage_percent > max_slippage_percent:
                        slippage_exceeded = True
                        slippage_msg = (
                            f"Slippage exceeded for {symbol} {side_value}: "
                            f"expected {expected_price}, got {avg_price}, "
                            f"slippage {actual_slippage_percent:.2f}% > max {max_slippage_percent}%"
                        )

                        if slippage_action == "reject":
                            logger.error(slippage_msg)
                            raise SlippageExceededError(slippage_msg)
                        else:
                            logger.warning(slippage_msg)
            
            if record_in_db and position_group_id:
                # Create a "virtual" leg index for tracking (e.g., -1 or derived from sequence)
                # But DCAOrder usually maps to a plan. Here we just want to track the fill.
                # We'll use a special leg_index -1 for ad-hoc market orders to differentiate.
                
                # Extract fill details
                filled_qty_raw = exchange_order_data.get("filled") or quantity
                filled_qty = Decimal(str(filled_qty_raw))
                avg_price_raw = exchange_order_data.get("average") or exchange_order_data.get("avg_price") or exchange_order_data.get("price") or "0"
                avg_price = Decimal(str(avg_price_raw)) if avg_price_raw else Decimal("0")

                # If avg_price is 0 (common in immediate response), might need to fetch order? 
                # For now, trust exchange or use 0 and let monitor fix it? 
                # Monitor doesn't monitor filled orders usually. 
                # Let's hope 'average' is populated or 'price' is.
                
                market_order = DCAOrder(
                    group_id=position_group_id,
                    pyramid_id=pyramid_id, # Use provided pyramid_id or None
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

    async def sync_orders_for_group(self, group_id: uuid.UUID):
        """
        Syncs all orders for a position group with the exchange to get accurate fill status.
        This should be called before closing a position to ensure we have up-to-date data.

        Only syncs orders that:
        1. Have an exchange_order_id (were submitted to exchange)
        2. Are not already in a terminal state (filled, cancelled)
        """
        orders = await self.dca_order_repository.get_all_orders_by_group_id(group_id)

        for order in orders:
            # Only sync orders that have been submitted to exchange and are not terminal
            if order.exchange_order_id and order.status in [
                OrderStatus.OPEN.value,
                OrderStatus.PARTIALLY_FILLED.value,
                OrderStatus.TRIGGER_PENDING.value
            ]:
                try:
                    await self.check_order_status(order)
                    logger.info(f"Synced order {order.id} ({order.symbol}): status={order.status}, filled={order.filled_quantity}")
                except Exception as e:
                    # Log but don't fail - order might already be cancelled/filled
                    logger.warning(f"Could not sync order {order.id}: {e}")

        # Flush to ensure all updates are visible
        await self.session.flush()

    async def cancel_open_orders_for_group(self, group_id: uuid.UUID):
        """
        Cancels all open orders for a group:
        1. Open/Partially Filled DCA orders (Entry orders).
        2. TP orders associated with Filled DCA orders.
        """
        # Fetch ALL orders for the group to ensure we catch TP orders on filled legs
        orders = await self.dca_order_repository.get_all_orders_by_group_id(group_id)
        
        for order in orders:
            # Cancel Entry Orders (including TRIGGER_PENDING which are stop orders on exchange)
            if order.status in [OrderStatus.OPEN.value, OrderStatus.PARTIALLY_FILLED.value, OrderStatus.TRIGGER_PENDING.value]:
                await self.cancel_order(order)
            
            # Cancel TP Orders for Filled entries
            elif order.status == OrderStatus.FILLED.value and order.tp_order_id:
                await self.cancel_tp_order(order)

    async def close_position_market(
        self,
        position_group: PositionGroup,
        quantity_to_close: Decimal,
        expected_price: Decimal = None,
        max_slippage_percent: float = None,
        slippage_action: str = "warn"
    ) -> Dict[str, Any]:
        """
        Closes a position (or partial quantity) using a market order.
        Determines the correct side (opposite of position side) automatically.

        Args:
            position_group: The position group to close
            quantity_to_close: Amount to close
            expected_price: Expected execution price for slippage calculation
            max_slippage_percent: Maximum allowed slippage percentage
            slippage_action: "warn" to log only, "reject" to raise SlippageExceededError

        Returns:
            Dict with order result including fee information
        """
        close_side = "SELL" if position_group.side == "long" else "BUY"

        order_result = await self.place_market_order(
            user_id=position_group.user_id,
            exchange=position_group.exchange,
            symbol=position_group.symbol,
            side=close_side,
            quantity=quantity_to_close,
            position_group_id=position_group.id,
            expected_price=expected_price,
            slippage_action=slippage_action,
            max_slippage_percent=max_slippage_percent
        )
        return order_result

