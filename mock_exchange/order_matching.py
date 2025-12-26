"""
Order matching engine for the mock exchange.
Handles limit order fills when prices change.
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from models import Order, Symbol, Balance, Position, Trade

logger = logging.getLogger(__name__)


class OrderMatchingEngine:
    """
    Simulates order matching when prices change.
    - MARKET orders: Fill immediately at current price
    - LIMIT orders: Fill when price reaches the limit
    - STOP_LOSS/TAKE_PROFIT: Trigger when price reaches stop level
    """

    def __init__(self, db: Session):
        self.db = db

    def process_market_order(self, order: Order) -> Tuple[bool, str]:
        """
        Process a market order - fills immediately at current price.
        Returns (success, message)
        """
        symbol = self.db.query(Symbol).filter(Symbol.symbol == order.symbol).first()
        if not symbol:
            return False, f"Symbol {order.symbol} not found"

        current_price = symbol.current_price
        if current_price <= 0:
            return False, f"Invalid price for {order.symbol}"

        # Fill the order
        return self._fill_order(order, current_price, order.quantity)

    def process_limit_order(self, order: Order) -> Tuple[bool, str]:
        """
        Check if a limit order should be filled based on current price.
        Returns (success, message)
        """
        symbol = self.db.query(Symbol).filter(Symbol.symbol == order.symbol).first()
        if not symbol:
            return False, f"Symbol {order.symbol} not found"

        current_price = symbol.current_price
        order_price = order.price

        # Check if limit order should fill
        should_fill = False
        if order.side.upper() == "BUY":
            # Buy limit fills when price <= order price
            should_fill = current_price <= order_price
        else:  # SELL
            # Sell limit fills when price >= order price
            should_fill = current_price >= order_price

        if should_fill:
            return self._fill_order(order, order_price, order.quantity)

        return False, "Price not reached"

    def process_stop_order(self, order: Order) -> Tuple[bool, str]:
        """
        Check if a stop order should be triggered.
        """
        symbol = self.db.query(Symbol).filter(Symbol.symbol == order.symbol).first()
        if not symbol:
            return False, f"Symbol {order.symbol} not found"

        current_price = symbol.current_price
        stop_price = order.stop_price

        # Check if stop should trigger
        should_trigger = False
        if order.side.upper() == "BUY":
            # Buy stop triggers when price >= stop price
            should_trigger = current_price >= stop_price
        else:  # SELL
            # Sell stop triggers when price <= stop price
            should_trigger = current_price <= stop_price

        if should_trigger:
            # For STOP_LOSS/TAKE_PROFIT market, fill at current price
            if "LIMIT" not in order.type.upper():
                return self._fill_order(order, current_price, order.quantity)
            else:
                # For stop-limit, fill at the limit price
                return self._fill_order(order, order.price, order.quantity)

        return False, "Stop price not reached"

    def _fill_order(
        self, order: Order, fill_price: float, fill_qty: float
    ) -> Tuple[bool, str]:
        """
        Fill an order and update balances/positions.
        """
        try:
            # Update order status
            order.executed_qty = fill_qty
            order.avg_price = fill_price
            order.status = "FILLED"
            order.updated_at = datetime.utcnow()

            # Calculate trade value
            trade_value = fill_price * fill_qty

            # Get API key balance
            balance = (
                self.db.query(Balance)
                .filter(
                    Balance.api_key_id == order.api_key_id, Balance.asset == "USDT"
                )
                .first()
            )

            if not balance:
                # Create balance if not exists
                balance = Balance(
                    api_key_id=order.api_key_id,
                    asset="USDT",
                    free=100000.0,
                    locked=0.0,
                    total=100000.0,
                )
                self.db.add(balance)

            # Update balance based on side
            if order.side.upper() == "BUY":
                # Buying: deduct USDT
                balance.free -= trade_value
                balance.locked = max(0, balance.locked - trade_value)
            else:
                # Selling: add USDT (closing position)
                balance.free += trade_value

            balance.total = balance.free + balance.locked

            # Update or create position
            self._update_position(order, fill_price, fill_qty)

            # Record trade
            trade = Trade(
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                price=fill_price,
                quantity=fill_qty,
                quote_qty=trade_value,
                commission=trade_value * 0.0004,  # 0.04% fee
                commission_asset="USDT",
                is_maker=order.type.upper() == "LIMIT",
            )
            self.db.add(trade)
            self.db.commit()

            logger.info(
                f"Filled order {order.id}: {order.side} {fill_qty} {order.symbol} @ {fill_price}"
            )
            return True, f"Order filled at {fill_price}"

        except Exception as e:
            logger.error(f"Error filling order: {e}")
            self.db.rollback()
            return False, str(e)

    def _update_position(self, order: Order, fill_price: float, fill_qty: float):
        """Update position after order fill."""
        position = (
            self.db.query(Position)
            .filter(
                Position.api_key_id == order.api_key_id,
                Position.symbol == order.symbol,
            )
            .first()
        )

        if order.side.upper() == "BUY":
            qty_delta = fill_qty
        else:
            qty_delta = -fill_qty

        if position:
            # Update existing position
            old_qty = position.quantity
            old_entry = position.entry_price
            new_qty = old_qty + qty_delta

            if new_qty != 0 and old_qty != 0 and (old_qty * new_qty > 0):
                # Same direction - average the entry price
                position.entry_price = (
                    (old_entry * abs(old_qty)) + (fill_price * abs(qty_delta))
                ) / abs(new_qty)
            elif new_qty != 0:
                # Direction change or new position
                position.entry_price = fill_price

            position.quantity = new_qty

            # If position is closed, calculate realized PnL
            if abs(new_qty) < abs(old_qty):
                # Partial or full close
                closed_qty = abs(old_qty) - abs(new_qty)
                if old_qty > 0:  # Was long
                    pnl = (fill_price - old_entry) * closed_qty
                else:  # Was short
                    pnl = (old_entry - fill_price) * closed_qty
                position.realized_pnl += pnl

            position.updated_at = datetime.utcnow()
        else:
            # Create new position
            position = Position(
                api_key_id=order.api_key_id,
                symbol=order.symbol,
                position_side=order.position_side or "BOTH",
                entry_price=fill_price,
                quantity=qty_delta,
                leverage=1,
            )
            self.db.add(position)

    def check_all_pending_orders(self) -> List[dict]:
        """
        Check all pending orders and fill those that meet conditions.
        Called when prices change.
        Returns list of filled order info.
        """
        filled_orders = []

        # Get all open orders
        open_orders = (
            self.db.query(Order)
            .filter(Order.status.in_(["NEW", "PARTIALLY_FILLED"]))
            .all()
        )

        for order in open_orders:
            success = False
            message = ""

            if order.type.upper() == "MARKET":
                success, message = self.process_market_order(order)
            elif order.type.upper() == "LIMIT":
                success, message = self.process_limit_order(order)
            elif order.type.upper() in [
                "STOP_LOSS",
                "STOP_LOSS_LIMIT",
                "TAKE_PROFIT",
                "TAKE_PROFIT_LIMIT",
            ]:
                success, message = self.process_stop_order(order)

            if success:
                filled_orders.append(
                    {
                        "order_id": order.id,
                        "symbol": order.symbol,
                        "side": order.side,
                        "price": order.avg_price,
                        "quantity": order.executed_qty,
                        "message": message,
                    }
                )

        return filled_orders

    def update_unrealized_pnl(self):
        """Update unrealized PnL for all positions based on current prices."""
        positions = self.db.query(Position).filter(Position.quantity != 0).all()

        for position in positions:
            symbol = (
                self.db.query(Symbol).filter(Symbol.symbol == position.symbol).first()
            )
            if symbol:
                current_price = symbol.current_price
                if position.quantity > 0:  # Long
                    position.unrealized_pnl = (
                        current_price - position.entry_price
                    ) * position.quantity
                else:  # Short
                    position.unrealized_pnl = (
                        position.entry_price - current_price
                    ) * abs(position.quantity)

        self.db.commit()
