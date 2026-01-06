#!/usr/bin/env python
"""
Test TP Duplicate Protection

This test validates that the _find_existing_tp_order safeguard correctly
prevents duplicate TP orders when a deadlock causes DB rollback after
a TP was already placed on the exchange.

Scenario tested:
1. Create a filled DCA order (simulating order fill)
2. Place TP order on exchange (simulating normal flow)
3. Simulate DB rollback (tp_order_id = NULL)
4. Attempt to place TP again
5. Verify safeguard detects existing TP and links it

Usage:
    python scripts/test_tp_duplicate_protection.py
"""
import asyncio
import logging
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

sys.path.insert(0, '.')

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.user import User
from app.repositories.dca_order import DCAOrderRepository
from app.services.order_management import OrderService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tp_duplicate_test")

TEST_PREFIX = "TP_DUP_TEST_"


class MockExchangeConnector:
    """
    Mock exchange connector that simulates TP order placement
    and tracks orders for duplicate detection testing.
    """

    def __init__(self):
        self.open_orders: List[Dict[str, Any]] = []
        self.order_counter = 0
        self.placed_orders: List[Dict[str, Any]] = []

    async def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        quantity: Decimal,
        price: Decimal = None
    ) -> Dict[str, Any]:
        """Simulate placing an order on exchange."""
        self.order_counter += 1
        order_id = f"MOCK_TP_{self.order_counter}"

        order = {
            "id": order_id,
            "symbol": symbol,
            "type": order_type.lower(),
            "side": side.lower(),
            "price": float(price) if price else None,
            "amount": float(quantity),
            "quantity": float(quantity),
            "status": "open",
            "filled": 0,
            "remaining": float(quantity),
        }

        self.open_orders.append(order)
        self.placed_orders.append(order.copy())

        logger.info(f"Mock exchange: Placed order {order_id} - {side} {quantity} @ {price}")
        return order

    async def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Return open orders, optionally filtered by symbol."""
        if symbol:
            return [o for o in self.open_orders if o["symbol"] == symbol]
        return self.open_orders

    async def get_precision_rules(self) -> Dict[str, Dict[str, Any]]:
        """Return mock precision rules."""
        return {
            f"{TEST_PREFIX}BTC": {"tick_size": "0.01", "lot_size": "0.001"},
        }

    async def close(self):
        """Mock close."""
        pass


async def create_engine_and_session():
    """Create database engine and session factory."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


async def get_test_user(session: AsyncSession) -> User:
    """Get a test user."""
    result = await session.execute(select(User).limit(1))
    return result.scalars().first()


async def create_test_position_and_order(session: AsyncSession, user: User) -> tuple:
    """Create a test position group and filled DCA order."""

    # Create position group
    position = PositionGroup(
        id=uuid.uuid4(),
        user_id=user.id,
        symbol=f"{TEST_PREFIX}BTC",
        exchange="mock",
        timeframe=1,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        base_entry_price=Decimal("50000.0"),
        weighted_avg_entry=Decimal("50000.0"),
        total_invested_usd=Decimal("1000.0"),
        total_filled_quantity=Decimal("0.02"),
        total_dca_legs=3,
        filled_dca_legs=1,
        pyramid_count=1,
        max_pyramids=3,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("2.0"),
    )
    session.add(position)

    # Create pyramid
    pyramid = Pyramid(
        id=uuid.uuid4(),
        group_id=position.id,
        pyramid_index=0,
        entry_price=Decimal("50000.0"),
        entry_timestamp=datetime.utcnow(),
        status=PyramidStatus.FILLED,
        dca_config={"levels": 3},
    )
    session.add(pyramid)

    # Create filled DCA order (this is what we'll test TP placement for)
    dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=position.id,
        pyramid_id=pyramid.id,
        symbol=f"{TEST_PREFIX}BTC",
        side="buy",
        order_type="limit",
        price=Decimal("50000.0"),
        quantity=Decimal("0.02"),
        filled_quantity=Decimal("0.02"),
        avg_fill_price=Decimal("50000.0"),
        status=OrderStatus.FILLED,
        leg_index=0,
        filled_at=datetime.utcnow(),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("50.0"),
        tp_percent=Decimal("2.0"),  # 2% TP
        tp_price=Decimal("51000.0"),  # Pre-calculated TP price
        tp_order_id=None,  # No TP placed yet
    )
    session.add(dca_order)

    await session.commit()
    await session.refresh(dca_order)

    logger.info(f"Created test position {position.id} and order {dca_order.id}")
    return position, dca_order


async def cleanup_test_data(session: AsyncSession):
    """Remove all test data."""
    await session.execute(
        text(f"DELETE FROM dca_orders WHERE symbol LIKE '{TEST_PREFIX}%'")
    )
    await session.execute(
        text(f"DELETE FROM pyramids WHERE group_id IN (SELECT id FROM position_groups WHERE symbol LIKE '{TEST_PREFIX}%')")
    )
    await session.execute(
        text(f"DELETE FROM position_groups WHERE symbol LIKE '{TEST_PREFIX}%'")
    )
    await session.commit()
    logger.info("Cleaned up test data")


async def run_test():
    """Run the TP duplicate protection test."""
    logger.info("=" * 70)
    logger.info("TP DUPLICATE PROTECTION TEST")
    logger.info("=" * 70)

    engine, session_factory = await create_engine_and_session()
    mock_exchange = MockExchangeConnector()

    try:
        async with session_factory() as session:
            # Cleanup any previous test data
            await cleanup_test_data(session)

            # Get test user
            user = await get_test_user(session)
            if not user:
                logger.error("No user found in database")
                return False

            # Create test position and order
            position, dca_order = await create_test_position_and_order(session, user)

            # Create order service with mock exchange
            dca_order_repo = DCAOrderRepository(session)
            order_service = OrderService(
                session=session,
                user=user,
                exchange_connector=mock_exchange
            )

            # ===== PHASE 1: Initial TP Placement =====
            logger.info("\n--- PHASE 1: Initial TP Placement ---")

            # Refresh order to get latest state
            await session.refresh(dca_order)

            # Place TP order (simulating normal flow)
            result = await order_service.place_tp_order(dca_order)
            await session.commit()

            if not result.tp_order_id:
                logger.error("FAIL: TP order was not placed!")
                return False

            first_tp_order_id = result.tp_order_id
            logger.info(f"First TP order placed: {first_tp_order_id}")
            logger.info(f"Exchange has {len(mock_exchange.open_orders)} open orders")

            # ===== PHASE 2: Simulate Deadlock Rollback =====
            logger.info("\n--- PHASE 2: Simulating Deadlock Rollback ---")

            # Simulate what happens during a deadlock rollback:
            # The tp_order_id gets set back to NULL in the database
            dca_order.tp_order_id = None
            await session.commit()

            logger.info(f"Simulated rollback: tp_order_id is now {dca_order.tp_order_id}")
            logger.info(f"But exchange still has {len(mock_exchange.open_orders)} open orders")

            # ===== PHASE 3: Attempt Second TP Placement =====
            logger.info("\n--- PHASE 3: Attempting Second TP Placement ---")

            # Refresh order to get the "rolled back" state
            await session.refresh(dca_order)

            # This should detect the existing TP and NOT create a duplicate
            result2 = await order_service.place_tp_order(dca_order)
            await session.commit()

            second_tp_order_id = result2.tp_order_id
            logger.info(f"Second TP attempt result: {second_tp_order_id}")

            # ===== PHASE 4: Verify Results =====
            logger.info("\n--- PHASE 4: Verification ---")

            total_orders_placed = len(mock_exchange.placed_orders)
            total_open_orders = len(mock_exchange.open_orders)

            logger.info(f"Total orders placed on exchange: {total_orders_placed}")
            logger.info(f"Total open orders on exchange: {total_open_orders}")
            logger.info(f"First TP order ID: {first_tp_order_id}")
            logger.info(f"Second TP order ID: {second_tp_order_id}")

            # Check results
            test_passed = True

            if total_orders_placed > 1:
                logger.error(f"FAIL: Duplicate TP was placed! Expected 1, got {total_orders_placed}")
                test_passed = False
            else:
                logger.info("PASS: Only one TP order was placed on exchange")

            if first_tp_order_id != second_tp_order_id:
                logger.error(f"FAIL: TP order IDs don't match! First: {first_tp_order_id}, Second: {second_tp_order_id}")
                test_passed = False
            else:
                logger.info("PASS: Both attempts linked to the same TP order")

            if not result2.tp_order_id:
                logger.error("FAIL: Second attempt didn't link to any TP order")
                test_passed = False
            else:
                logger.info("PASS: Order has tp_order_id set correctly")

            # Cleanup
            await cleanup_test_data(session)

            return test_passed

    finally:
        await engine.dispose()


async def run_edge_case_tests():
    """Run additional edge case tests."""
    logger.info("\n" + "=" * 70)
    logger.info("EDGE CASE TESTS")
    logger.info("=" * 70)

    engine, session_factory = await create_engine_and_session()

    try:
        async with session_factory() as session:
            await cleanup_test_data(session)

            user = await get_test_user(session)
            if not user:
                return False

            position, dca_order = await create_test_position_and_order(session, user)

            # ===== Test: No existing orders on exchange =====
            logger.info("\n--- Edge Case: No existing orders on exchange ---")

            mock_exchange = MockExchangeConnector()
            order_service = OrderService(
                session=session,
                user=user,
                exchange_connector=mock_exchange
            )

            # Should place a new TP since there are no existing orders
            result = await order_service.place_tp_order(dca_order)
            await session.commit()

            if result.tp_order_id and len(mock_exchange.placed_orders) == 1:
                logger.info("PASS: New TP placed when no existing orders")
            else:
                logger.error("FAIL: Expected new TP to be placed")
                return False

            # ===== Test: Existing order with different price =====
            logger.info("\n--- Edge Case: Existing order with different price ---")

            # Reset
            await cleanup_test_data(session)
            position, dca_order = await create_test_position_and_order(session, user)

            mock_exchange2 = MockExchangeConnector()
            # Add an existing order with a very different price (not our TP)
            mock_exchange2.open_orders.append({
                "id": "OTHER_ORDER_123",
                "symbol": f"{TEST_PREFIX}BTC",
                "type": "limit",
                "side": "sell",
                "price": 60000.0,  # Way different from expected ~51000
                "amount": 0.02,
                "quantity": 0.02,
            })

            order_service2 = OrderService(
                session=session,
                user=user,
                exchange_connector=mock_exchange2
            )

            result2 = await order_service2.place_tp_order(dca_order)
            await session.commit()

            # Should place a new TP since existing order doesn't match
            if result2.tp_order_id and result2.tp_order_id != "OTHER_ORDER_123":
                logger.info("PASS: New TP placed when existing order price doesn't match")
            else:
                logger.error("FAIL: Incorrectly linked to non-matching order")
                return False

            await cleanup_test_data(session)
            return True

    finally:
        await engine.dispose()


def main():
    """Run all tests."""
    logger.info("Starting TP Duplicate Protection Tests\n")

    # Run main test
    main_test_passed = asyncio.run(run_test())

    # Run edge case tests
    edge_tests_passed = asyncio.run(run_edge_case_tests())

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    if main_test_passed and edge_tests_passed:
        logger.info("ALL TESTS PASSED")
        logger.info("")
        logger.info("The TP duplicate protection safeguard correctly:")
        logger.info("  1. Detects existing TP orders on exchange")
        logger.info("  2. Links to existing TP instead of creating duplicates")
        logger.info("  3. Places new TP when no matching order exists")
        logger.info("  4. Ignores orders with different prices")
        sys.exit(0)
    else:
        logger.error("SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
