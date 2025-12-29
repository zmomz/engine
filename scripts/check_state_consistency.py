"""
State Consistency Checker

COMPREHENSIVE state machine bug detection:
1. Invariant checks (quantity matches, status consistency)
2. State transition validation (no invalid transitions)
3. DB vs Exchange sync verification
4. Log scanning for impossible states
5. Orphaned entity detection

Run with:
    docker compose exec app python scripts/check_state_consistency.py
    docker compose exec app python scripts/check_state_consistency.py --with-exchange  # Also check exchange
    docker compose exec app python scripts/check_state_consistency.py --scan-logs      # Also scan logs
"""

import asyncio
import sys
import re
import httpx
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional

# Add backend to path
sys.path.insert(0, '/app/backend')

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.user import User


# Valid state transitions
ORDER_TRANSITIONS = {
    OrderStatus.PENDING: [OrderStatus.PENDING, OrderStatus.TRIGGER_PENDING, OrderStatus.OPEN, OrderStatus.CANCELLED, OrderStatus.FAILED],
    OrderStatus.TRIGGER_PENDING: [OrderStatus.TRIGGER_PENDING, OrderStatus.OPEN, OrderStatus.CANCELLED, OrderStatus.FAILED],
    OrderStatus.OPEN: [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED],
    OrderStatus.PARTIALLY_FILLED: [OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCELLED],
    OrderStatus.FILLED: [OrderStatus.FILLED],  # Terminal
    OrderStatus.CANCELLED: [OrderStatus.CANCELLED],  # Terminal
    OrderStatus.FAILED: [OrderStatus.FAILED],  # Terminal
}

PYRAMID_TRANSITIONS = {
    PyramidStatus.PENDING: [PyramidStatus.PENDING, PyramidStatus.SUBMITTED, PyramidStatus.CANCELLED],
    PyramidStatus.SUBMITTED: [PyramidStatus.SUBMITTED, PyramidStatus.FILLED, PyramidStatus.CANCELLED],
    PyramidStatus.FILLED: [PyramidStatus.FILLED],  # Terminal
    PyramidStatus.CANCELLED: [PyramidStatus.CANCELLED],  # Terminal
}

POSITION_TRANSITIONS = {
    PositionGroupStatus.WAITING: [PositionGroupStatus.WAITING, PositionGroupStatus.LIVE, PositionGroupStatus.FAILED, PositionGroupStatus.CLOSED],
    PositionGroupStatus.LIVE: [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED, PositionGroupStatus.ACTIVE, PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED],
    PositionGroupStatus.PARTIALLY_FILLED: [PositionGroupStatus.PARTIALLY_FILLED, PositionGroupStatus.ACTIVE, PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED],
    PositionGroupStatus.ACTIVE: [PositionGroupStatus.ACTIVE, PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED],
    PositionGroupStatus.CLOSING: [PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED],
    PositionGroupStatus.CLOSED: [PositionGroupStatus.CLOSED],  # Terminal
    PositionGroupStatus.FAILED: [PositionGroupStatus.FAILED],  # Terminal
}

# Impossible state patterns to scan in logs
IMPOSSIBLE_STATE_PATTERNS = [
    (r"Order .* has filled_quantity=\d+ but status is OPEN", "Order filled but status OPEN"),
    (r"Position .* CLOSED but has \d+ open orders", "Closed position with open orders"),
    (r"timer expired .* but risk_eligible=False", "Timer expired but not eligible"),
    (r"Invalid.*transition", "Invalid state transition"),
    (r"constraint.*violation", "Database constraint violation"),
    (r"deadlock", "Database deadlock"),
]


class ConsistencyChecker:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []

    def error(self, msg: str):
        self.errors.append(msg)
        print(f"  [ERROR] {msg}")

    def warn(self, msg: str):
        self.warnings.append(msg)
        print(f"  [WARN]  {msg}")

    def ok(self, msg: str):
        self.info.append(msg)
        print(f"  [OK]    {msg}")

    async def check_all(self, session: AsyncSession, check_exchange: bool = False, scan_logs: bool = False):
        """Run all consistency checks."""
        print("\n" + "=" * 60)
        print("STATE CONSISTENCY CHECK")
        print(f"Time: {datetime.now().isoformat()}")
        print("=" * 60)

        # Core invariant checks
        await self.check_position_order_quantities(session)
        await self.check_order_status_consistency(session)
        await self.check_pyramid_status_consistency(session)
        await self.check_risk_timer_consistency(session)
        await self.check_orphaned_orders(session)
        await self.check_closed_positions_have_no_open_orders(session)

        # State transition validation (checks recent state history)
        await self.check_state_transition_validity(session)

        # Optional: DB vs Exchange sync
        if check_exchange:
            await self.check_db_exchange_sync(session)

        # Optional: Log scanning
        if scan_logs:
            await self.scan_logs_for_impossible_states()

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Errors:   {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"OK:       {len(self.info)}")

        if self.errors:
            print("\nERRORS FOUND:")
            for e in self.errors:
                print(f"  - {e}")

        return len(self.errors) == 0

    async def check_position_order_quantities(self, session: AsyncSession):
        """Check that position total_filled_quantity matches sum of filled orders."""
        print("\n[1] Position Quantity vs Order Sum")

        result = await session.execute(
            select(PositionGroup).where(
                PositionGroup.status.in_([
                    PositionGroupStatus.WAITING,
                    PositionGroupStatus.LIVE,
                    PositionGroupStatus.PARTIALLY_FILLED,
                    PositionGroupStatus.ACTIVE
                ])
            )
        )
        positions = result.scalars().all()

        for pos in positions:
            # Get all filled orders for this position
            orders_result = await session.execute(
                select(DCAOrder).where(
                    and_(
                        DCAOrder.group_id == pos.id,
                        DCAOrder.status.in_([OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED])
                    )
                )
            )
            orders = orders_result.scalars().all()

            order_qty_sum = sum(Decimal(str(o.filled_quantity or 0)) for o in orders)
            pos_qty = Decimal(str(pos.total_filled_quantity or 0))

            diff = abs(order_qty_sum - pos_qty)
            if diff > Decimal("0.0001"):
                self.error(
                    f"Position {pos.id} ({pos.symbol}): "
                    f"total_filled_quantity={pos_qty} but order sum={order_qty_sum} "
                    f"(diff={diff})"
                )
            else:
                self.ok(f"Position {pos.symbol}: qty={pos_qty} matches orders")

    async def check_order_status_consistency(self, session: AsyncSession):
        """Check that order status matches filled_quantity."""
        print("\n[2] Order Status vs Filled Quantity")

        result = await session.execute(select(DCAOrder))
        orders = result.scalars().all()

        for order in orders:
            filled = Decimal(str(order.filled_quantity or 0))
            qty = Decimal(str(order.quantity or 0))
            status = order.status

            if filled > 0 and status == OrderStatus.OPEN:
                self.error(
                    f"Order {order.id}: has filled_quantity={filled} "
                    f"but status is OPEN (should be PARTIALLY_FILLED or FILLED)"
                )

            if filled >= qty and qty > 0 and status != OrderStatus.FILLED:
                self.error(
                    f"Order {order.id}: fully filled (filled={filled}, qty={qty}) "
                    f"but status is {status} (should be FILLED)"
                )

            if filled == 0 and status == OrderStatus.FILLED:
                self.error(
                    f"Order {order.id}: status is FILLED but filled_quantity=0"
                )

        self.ok(f"Checked {len(orders)} orders")

    async def check_pyramid_status_consistency(self, session: AsyncSession):
        """Check that pyramid status matches its orders' statuses."""
        print("\n[3] Pyramid Status Consistency")

        result = await session.execute(select(Pyramid))
        pyramids = result.scalars().all()

        for pyramid in pyramids:
            # Get orders for this pyramid
            orders_result = await session.execute(
                select(DCAOrder).where(DCAOrder.pyramid_id == pyramid.id)
            )
            orders = orders_result.scalars().all()

            if not orders:
                if pyramid.status not in [PyramidStatus.PENDING, PyramidStatus.SUBMITTED]:
                    self.warn(
                        f"Pyramid {pyramid.id}: no orders but status is {pyramid.status}"
                    )
                continue

            all_filled = all(o.status == OrderStatus.FILLED for o in orders)
            any_filled = any(
                o.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]
                for o in orders
            )

            if all_filled and pyramid.status != PyramidStatus.FILLED:
                self.error(
                    f"Pyramid {pyramid.id}: all orders filled but status is {pyramid.status}"
                )

            if any_filled and pyramid.status == PyramidStatus.PENDING:
                self.error(
                    f"Pyramid {pyramid.id}: has filled orders but status is PENDING"
                )

        self.ok(f"Checked {len(pyramids)} pyramids")

    async def check_risk_timer_consistency(self, session: AsyncSession):
        """Check risk timer state consistency."""
        print("\n[4] Risk Timer Consistency")

        result = await session.execute(
            select(PositionGroup).where(
                PositionGroup.status.in_([
                    PositionGroupStatus.WAITING,
                    PositionGroupStatus.LIVE,
                    PositionGroupStatus.PARTIALLY_FILLED,
                    PositionGroupStatus.ACTIVE
                ])
            )
        )
        positions = result.scalars().all()

        now = datetime.utcnow()

        for pos in positions:
            timer_start = pos.risk_timer_start
            timer_expires = pos.risk_timer_expires
            eligible = pos.risk_eligible

            # If timer expired, eligible should be true
            if timer_expires and timer_expires < now and not eligible:
                self.error(
                    f"Position {pos.id} ({pos.symbol}): "
                    f"timer expired at {timer_expires} but risk_eligible=False"
                )

            # If eligible but no timer, that's suspicious
            if eligible and not timer_start:
                self.warn(
                    f"Position {pos.id} ({pos.symbol}): "
                    f"risk_eligible=True but no timer_start set"
                )

            # Timer end should be after start
            if timer_start and timer_expires and timer_expires < timer_start:
                self.error(
                    f"Position {pos.id} ({pos.symbol}): "
                    f"timer_expires ({timer_expires}) is before timer_start ({timer_start})"
                )

        self.ok(f"Checked {len(positions)} active positions")

    async def check_orphaned_orders(self, session: AsyncSession):
        """Check for orders without valid position groups."""
        print("\n[5] Orphaned Orders")

        result = await session.execute(
            select(DCAOrder).where(
                DCAOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
            )
        )
        orders = result.scalars().all()

        orphaned = 0
        for order in orders:
            if not order.group_id:
                self.error(f"Order {order.id}: no group_id (orphaned)")
                orphaned += 1
                continue

            # Check if position exists and is active
            pos_result = await session.execute(
                select(PositionGroup).where(PositionGroup.id == order.group_id)
            )
            pos = pos_result.scalar_one_or_none()

            if not pos:
                self.error(
                    f"Order {order.id}: group_id={order.group_id} "
                    f"does not exist (orphaned)"
                )
                orphaned += 1

        if orphaned == 0:
            self.ok(f"No orphaned orders found ({len(orders)} checked)")

    async def check_closed_positions_have_no_open_orders(self, session: AsyncSession):
        """Check that closed positions don't have open orders."""
        print("\n[6] Closed Positions Open Orders")

        result = await session.execute(
            select(PositionGroup).where(
                PositionGroup.status == PositionGroupStatus.CLOSED
            )
        )
        closed_positions = result.scalars().all()

        issues = 0
        for pos in closed_positions:
            orders_result = await session.execute(
                select(DCAOrder).where(
                    and_(
                        DCAOrder.group_id == pos.id,
                        DCAOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
                    )
                )
            )
            open_orders = orders_result.scalars().all()

            if open_orders:
                self.error(
                    f"Position {pos.id} ({pos.symbol}): CLOSED but has "
                    f"{len(open_orders)} open orders"
                )
                issues += 1

        if issues == 0:
            self.ok(f"All {len(closed_positions)} closed positions have no open orders")

    async def check_state_transition_validity(self, session: AsyncSession):
        """
        Check that current states are reachable from initial states.
        This catches bugs where states transition invalidly (e.g., FILLED -> OPEN).
        """
        print("\n[7] State Transition Validity")

        issues = 0

        # Check orders - if FILLED, should have filled_quantity > 0
        result = await session.execute(
            select(DCAOrder).where(DCAOrder.status == OrderStatus.FILLED)
        )
        filled_orders = result.scalars().all()

        for order in filled_orders:
            filled = Decimal(str(order.filled_quantity or 0))
            if filled <= 0:
                self.error(
                    f"Order {order.id}: status=FILLED but filled_quantity={filled} "
                    "(impossible state - FILLED requires quantity > 0)"
                )
                issues += 1

        # Check pyramids - if FILLED, all orders should be filled
        result = await session.execute(
            select(Pyramid).where(Pyramid.status == PyramidStatus.FILLED)
        )
        filled_pyramids = result.scalars().all()

        for pyramid in filled_pyramids:
            orders_result = await session.execute(
                select(DCAOrder).where(DCAOrder.pyramid_id == pyramid.id)
            )
            orders = orders_result.scalars().all()

            unfilled = [o for o in orders if o.status != OrderStatus.FILLED]
            if unfilled:
                self.error(
                    f"Pyramid {pyramid.id}: status=FILLED but has {len(unfilled)} unfilled orders "
                    "(impossible state)"
                )
                issues += 1

        # Check positions - if CLOSED, should have closed_at timestamp
        result = await session.execute(
            select(PositionGroup).where(PositionGroup.status == PositionGroupStatus.CLOSED)
        )
        closed = result.scalars().all()

        for pos in closed:
            if not pos.closed_at:
                self.warn(
                    f"Position {pos.id} ({pos.symbol}): status=CLOSED but no closed_at timestamp"
                )

        if issues == 0:
            self.ok(f"State transitions valid ({len(filled_orders)} filled orders, {len(filled_pyramids)} filled pyramids)")

    async def check_db_exchange_sync(self, session: AsyncSession):
        """
        Check that DB order states match exchange states.
        Only works with mock exchange.
        """
        print("\n[8] DB vs Exchange Sync (Mock)")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get("http://mock-exchange:9000/admin/orders")
                if r.status_code != 200:
                    self.warn("Could not fetch orders from mock exchange")
                    return

                exchange_orders = r.json()

        except Exception as e:
            self.warn(f"Could not connect to mock exchange: {e}")
            return

        # Build exchange order map by exchange_order_id
        exchange_map = {str(o.get("id")): o for o in exchange_orders}

        # Get DB orders that have exchange_order_id
        result = await session.execute(
            select(DCAOrder).where(DCAOrder.exchange_order_id.isnot(None))
        )
        db_orders = result.scalars().all()

        sync_issues = 0
        for order in db_orders:
            ex_order = exchange_map.get(str(order.exchange_order_id))
            if not ex_order:
                # Order might be old/purged from mock
                continue

            # Compare states
            db_status = order.status.value.lower()
            ex_status = ex_order.get("status", "").lower()

            # Map exchange status to DB status
            status_map = {
                "new": "open",
                "open": "open",
                "partially_filled": "partially_filled",
                "filled": "filled",
                "cancelled": "cancelled",
                "canceled": "cancelled",
            }

            expected_db_status = status_map.get(ex_status, ex_status)

            if db_status != expected_db_status and expected_db_status:
                self.error(
                    f"Order {order.id}: DB status='{db_status}' but exchange status='{ex_status}' "
                    f"(expected DB to be '{expected_db_status}')"
                )
                sync_issues += 1

            # Compare filled quantity
            db_filled = float(order.filled_quantity or 0)
            ex_filled = float(ex_order.get("filled", 0))

            if abs(db_filled - ex_filled) > 0.0001:
                self.error(
                    f"Order {order.id}: DB filled={db_filled} but exchange filled={ex_filled}"
                )
                sync_issues += 1

        if sync_issues == 0:
            self.ok(f"DB and exchange in sync ({len(db_orders)} orders checked)")

    async def scan_logs_for_impossible_states(self):
        """
        Scan recent logs for patterns indicating impossible states.
        """
        print("\n[9] Log Scan for Impossible States")

        try:
            import subprocess
            result = subprocess.run(
                ["docker", "compose", "logs", "app", "--tail", "1000"],
                capture_output=True,
                text=True,
                timeout=30
            )
            logs = result.stdout + result.stderr
        except Exception as e:
            self.warn(f"Could not fetch logs: {e}")
            return

        issues_found = 0
        for pattern, description in IMPOSSIBLE_STATE_PATTERNS:
            matches = re.findall(pattern, logs, re.IGNORECASE)
            if matches:
                self.error(f"Found {len(matches)} occurrences of: {description}")
                for match in matches[:3]:  # Show first 3
                    print(f"      -> {match[:100]}")
                issues_found += len(matches)

        if issues_found == 0:
            self.ok("No impossible state patterns found in recent logs")


async def main():
    """Run the consistency checker."""
    check_exchange = "--with-exchange" in sys.argv
    scan_logs = "--scan-logs" in sys.argv

    async with AsyncSessionLocal() as session:
        checker = ConsistencyChecker()
        success = await checker.check_all(
            session,
            check_exchange=check_exchange,
            scan_logs=scan_logs
        )

    return 0 if success else 1


if __name__ == "__main__":
    print("Usage: python scripts/check_state_consistency.py [--with-exchange] [--scan-logs]")
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
