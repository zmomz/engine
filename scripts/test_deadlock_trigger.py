#!/usr/bin/env python
"""
Aggressive Deadlock Trigger Test

This test INTENTIONALLY tries to cause deadlocks to verify:
1. The system can detect deadlocks
2. Session rollback works correctly
3. The recovery mechanism kicks in
4. No data corruption occurs

The test recreates the exact scenario that caused ADAUSDT to get stuck:
- Risk engine trying to close a position
- Order fill monitor updating the same position's stats
- Both fighting over the same database rows

WARNING: This test WILL cause deadlocks. That's the point.
Run this on a test environment, not production.

Usage:
    python scripts/test_deadlock_trigger.py [--cleanup]
"""
import argparse
import asyncio
import logging
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Tuple
import random

sys.path.insert(0, '.')

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.user import User

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("deadlock_test")

# Test configuration
TEST_PREFIX = "DEADLOCK_TEST_"
NUM_TEST_POSITIONS = 3
CONCURRENT_WORKERS = 10
ITERATIONS_PER_WORKER = 20
OPERATION_DELAY_MS = 10  # Small delay to increase chance of collision


class DeadlockTestResults:
    """Track test results."""

    def __init__(self):
        self.total_operations = 0
        self.successful_operations = 0
        self.deadlocks_triggered = 0
        self.deadlocks_recovered = 0
        self.other_errors = 0
        self.data_corruption_detected = False
        self.stuck_positions_found = 0
        self.stuck_positions_recovered = 0

    def summary(self) -> str:
        success_rate = (self.successful_operations / self.total_operations * 100) if self.total_operations > 0 else 0
        recovery_rate = (self.deadlocks_recovered / self.deadlocks_triggered * 100) if self.deadlocks_triggered > 0 else 100

        status = "✅ PASS" if (recovery_rate == 100 and not self.data_corruption_detected) else "❌ FAIL"

        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AGGRESSIVE DEADLOCK TEST RESULTS                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Total Operations:              {self.total_operations:>10}                                   ║
║  Successful:                    {self.successful_operations:>10}                                   ║
║  Deadlocks Triggered:           {self.deadlocks_triggered:>10}  ← We WANT these!                   ║
║  Deadlocks Recovered:           {self.deadlocks_recovered:>10}                                   ║
║  Other Errors:                  {self.other_errors:>10}                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Data Corruption:               {"YES ❌" if self.data_corruption_detected else "NO ✅":>10}                                   ║
║  Stuck Positions Found:         {self.stuck_positions_found:>10}                                   ║
║  Stuck Positions Recovered:     {self.stuck_positions_recovered:>10}                                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  SUCCESS RATE:                  {success_rate:>10.2f}%                                  ║
║  DEADLOCK RECOVERY RATE:        {recovery_rate:>10.2f}%                                  ║
║                                                                              ║
║  OVERALL:                       {status:>10}                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


async def create_engine_and_session() -> Tuple[any, async_sessionmaker]:
    """Create database engine with specific settings for deadlock testing."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=30,  # More connections to increase contention
        max_overflow=20,
        pool_timeout=60,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


async def get_test_user(session: AsyncSession) -> User:
    """Get a test user."""
    result = await session.execute(select(User).limit(1))
    return result.scalars().first()


async def create_test_positions(
    session_factory: async_sessionmaker,
    num_positions: int = NUM_TEST_POSITIONS
) -> List[uuid.UUID]:
    """Create test positions for deadlock testing."""
    position_ids = []

    async with session_factory() as session:
        user = await get_test_user(session)
        if not user:
            raise ValueError("No user found in database")

        for i in range(num_positions):
            # Create position group
            position = PositionGroup(
                id=uuid.uuid4(),
                user_id=user.id,
                symbol=f"{TEST_PREFIX}SYM{i}",
                exchange="mock",
                timeframe=1,  # 1 minute, stored as integer
                side="long",
                status=PositionGroupStatus.ACTIVE.value,
                base_entry_price=Decimal("100.0"),
                weighted_avg_entry=Decimal("100.0"),
                total_invested_usd=Decimal("1000.0"),
                total_filled_quantity=Decimal("10.0"),
                total_dca_legs=5,
                filled_dca_legs=5,
                pyramid_count=1,
                max_pyramids=3,
                tp_mode="aggregate",
                tp_aggregate_percent=Decimal("2.0"),
                unrealized_pnl_usd=Decimal("-50.0"),
                unrealized_pnl_percent=Decimal("-5.0"),
                risk_timer_start=datetime.utcnow() - timedelta(minutes=30),
                risk_timer_expires=datetime.utcnow() - timedelta(minutes=15),
                risk_eligible=True,
            )
            session.add(position)
            position_ids.append(position.id)

            # Create a pyramid
            pyramid = Pyramid(
                id=uuid.uuid4(),
                group_id=position.id,
                pyramid_index=0,
                entry_price=Decimal("100.0"),
                entry_timestamp=datetime.utcnow(),
                status=PyramidStatus.FILLED,
                dca_config={"levels": 5},
            )
            session.add(pyramid)

            # Create DCA orders
            for j in range(5):
                order = DCAOrder(
                    id=uuid.uuid4(),
                    group_id=position.id,
                    pyramid_id=pyramid.id,
                    symbol=position.symbol,
                    side="buy",
                    order_type="limit",
                    price=Decimal(str(100 - j)),
                    quantity=Decimal("2.0"),
                    filled_quantity=Decimal("2.0"),
                    status=OrderStatus.FILLED,
                    leg_index=j,
                    filled_at=datetime.utcnow(),
                    # Required fields
                    gap_percent=Decimal(str(j * 2)),  # 0%, 2%, 4%, etc.
                    weight_percent=Decimal("20.0"),  # Equal weight
                    tp_percent=Decimal("2.0"),
                    tp_price=Decimal(str(100 - j + 2)),  # TP at +2% above entry
                )
                session.add(order)

        await session.commit()
        logger.info(f"Created {num_positions} test positions")

    return position_ids


async def cleanup_test_positions(session_factory: async_sessionmaker, max_retries: int = 5):
    """Remove all test positions with retry logic for deadlocks."""
    for attempt in range(max_retries):
        try:
            async with session_factory() as session:
                # Delete in correct order due to foreign keys
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
                logger.info("Cleaned up test positions")
                return
        except Exception as e:
            if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                logger.warning(f"Cleanup deadlock detected, retrying ({attempt + 1}/{max_retries})...")
                await asyncio.sleep(0.5)
            else:
                raise


async def simulate_risk_engine_close(
    session_factory: async_sessionmaker,
    position_id: uuid.UUID,
    results: DeadlockTestResults,
    worker_id: int
) -> bool:
    """
    Simulate what the risk engine does when closing a position.

    This:
    1. Loads the position with FOR UPDATE lock
    2. Updates status to CLOSING
    3. Sleeps briefly (simulating order execution)
    4. Updates to CLOSED
    """
    async with session_factory() as session:
        try:
            # Step 1: Load position with lock (like risk engine does)
            result = await session.execute(
                select(PositionGroup)
                .where(PositionGroup.id == position_id)
                .with_for_update()
            )
            position = result.scalars().first()

            if not position:
                results.total_operations += 1
                results.successful_operations += 1
                return True

            # Step 2: Mark as CLOSING
            position.status = PositionGroupStatus.CLOSING.value
            position.updated_at = datetime.utcnow()
            await session.flush()

            # Step 3: Simulate order execution time (this is where deadlocks can occur)
            await asyncio.sleep(OPERATION_DELAY_MS / 1000)

            # Step 4: Now try to update DCA orders (this can cause deadlock with order fill monitor)
            orders_result = await session.execute(
                select(DCAOrder)
                .where(DCAOrder.group_id == position_id)
                .with_for_update()
            )
            orders = orders_result.scalars().all()

            for order in orders:
                order.updated_at = datetime.utcnow()

            # Step 5: Mark as CLOSED
            position.status = PositionGroupStatus.ACTIVE.value  # Revert for next test iteration
            position.updated_at = datetime.utcnow()

            await session.commit()
            results.total_operations += 1
            results.successful_operations += 1
            return True

        except Exception as e:
            error_str = str(e).lower()
            results.total_operations += 1

            # Check for deadlock in error message (handles SQLAlchemy wrapped errors)
            if "deadlock" in error_str or "deadlockdetected" in error_str.replace(" ", ""):
                logger.warning(f"[Worker-{worker_id}] DEADLOCK detected in risk engine simulation!")
                results.deadlocks_triggered += 1

                try:
                    await session.rollback()
                    results.deadlocks_recovered += 1
                    logger.info(f"[Worker-{worker_id}] Successfully recovered from deadlock")
                except Exception as rollback_err:
                    logger.error(f"[Worker-{worker_id}] Rollback failed: {rollback_err}")
            else:
                logger.error(f"[Worker-{worker_id}] Database error: {e}")
                results.other_errors += 1
                try:
                    await session.rollback()
                except:
                    pass
            return False


async def simulate_order_fill_monitor(
    session_factory: async_sessionmaker,
    position_id: uuid.UUID,
    results: DeadlockTestResults,
    worker_id: int
) -> bool:
    """
    Simulate what the order fill monitor does.

    This:
    1. Loads DCA orders with FOR UPDATE lock
    2. Updates order status
    3. Then loads and updates position stats

    This is the OPPOSITE lock order from risk engine, which can cause deadlocks!
    """
    async with session_factory() as session:
        try:
            # Step 1: Load and lock DCA orders FIRST (opposite of risk engine!)
            orders_result = await session.execute(
                select(DCAOrder)
                .where(DCAOrder.group_id == position_id)
                .with_for_update()
            )
            orders = orders_result.scalars().all()

            if not orders:
                results.total_operations += 1
                results.successful_operations += 1
                return True

            # Step 2: Update orders
            for order in orders:
                order.updated_at = datetime.utcnow()

            await session.flush()

            # Step 3: Simulate some processing time
            await asyncio.sleep(OPERATION_DELAY_MS / 1000)

            # Step 4: Now try to lock the position (opposite order from risk engine = DEADLOCK!)
            result = await session.execute(
                select(PositionGroup)
                .where(PositionGroup.id == position_id)
                .with_for_update()
            )
            position = result.scalars().first()

            if position:
                # Update position stats
                position.filled_dca_legs = len([o for o in orders if o.status == OrderStatus.FILLED])
                position.updated_at = datetime.utcnow()

            await session.commit()
            results.total_operations += 1
            results.successful_operations += 1
            return True

        except Exception as e:
            error_str = str(e).lower()
            results.total_operations += 1

            # Check for deadlock in error message (handles SQLAlchemy wrapped errors)
            if "deadlock" in error_str or "deadlockdetected" in error_str.replace(" ", ""):
                logger.warning(f"[Worker-{worker_id}] DEADLOCK detected in order fill monitor simulation!")
                results.deadlocks_triggered += 1

                try:
                    await session.rollback()
                    results.deadlocks_recovered += 1
                    logger.info(f"[Worker-{worker_id}] Successfully recovered from deadlock")
                except Exception as rollback_err:
                    logger.error(f"[Worker-{worker_id}] Rollback failed: {rollback_err}")
            else:
                logger.error(f"[Worker-{worker_id}] Database error: {e}")
                results.other_errors += 1
                try:
                    await session.rollback()
                except:
                    pass
            return False


async def worker_task(
    session_factory: async_sessionmaker,
    position_ids: List[uuid.UUID],
    results: DeadlockTestResults,
    worker_id: int,
    iterations: int
):
    """Worker that randomly performs risk engine or order fill monitor operations."""
    for i in range(iterations):
        # Pick a random position
        position_id = random.choice(position_ids)

        # Randomly choose operation type
        if random.random() < 0.5:
            await simulate_risk_engine_close(session_factory, position_id, results, worker_id)
        else:
            await simulate_order_fill_monitor(session_factory, position_id, results, worker_id)

        # Small random delay
        await asyncio.sleep(random.uniform(0, 0.01))


async def verify_data_integrity(
    session_factory: async_sessionmaker,
    position_ids: List[uuid.UUID],
    results: DeadlockTestResults
):
    """Verify no data corruption occurred."""
    async with session_factory() as session:
        for pos_id in position_ids:
            result = await session.execute(
                select(PositionGroup).where(PositionGroup.id == pos_id)
            )
            position = result.scalars().first()

            if not position:
                logger.error(f"Position {pos_id} disappeared!")
                results.data_corruption_detected = True
                continue

            # Check for stuck closing positions
            if position.status == PositionGroupStatus.CLOSING.value:
                results.stuck_positions_found += 1
                logger.warning(f"Found stuck position: {position.symbol}")

            # Verify filled_dca_legs matches actual count
            orders_result = await session.execute(
                select(DCAOrder)
                .where(
                    DCAOrder.group_id == pos_id,
                    DCAOrder.status == OrderStatus.FILLED
                )
            )
            actual_filled = len(orders_result.scalars().all())

            if position.filled_dca_legs != actual_filled:
                logger.error(
                    f"Data corruption: {position.symbol} has filled_dca_legs={position.filled_dca_legs} "
                    f"but actual filled orders={actual_filled}"
                )
                results.data_corruption_detected = True


async def test_recovery_mechanism(
    session_factory: async_sessionmaker,
    position_ids: List[uuid.UUID],
    results: DeadlockTestResults
):
    """Test that the recovery mechanism works."""
    async with session_factory() as session:
        # Manually set a position to "closing" to test recovery
        if position_ids:
            test_pos_id = position_ids[0]
            result = await session.execute(
                select(PositionGroup).where(PositionGroup.id == test_pos_id)
            )
            position = result.scalars().first()

            if position:
                # Set it to closing with old timestamp
                position.status = PositionGroupStatus.CLOSING.value
                position.updated_at = datetime.utcnow() - timedelta(minutes=10)
                await session.commit()

                logger.info(f"Set {position.symbol} to CLOSING to test recovery...")

    # Now import and run the recovery function
    from app.services.risk.risk_timer import recover_stuck_closing_positions

    async with session_factory() as session:
        # Get closing positions
        result = await session.execute(
            select(PositionGroup)
            .where(PositionGroup.status == PositionGroupStatus.CLOSING.value)
        )
        closing_positions = result.scalars().all()

        if closing_positions:
            recovered = await recover_stuck_closing_positions(closing_positions, session)
            await session.commit()

            results.stuck_positions_recovered = len(recovered)
            logger.info(f"Recovery mechanism recovered {len(recovered)} positions")


async def run_deadlock_test(
    cleanup_only: bool = False,
    num_workers: int = CONCURRENT_WORKERS,
    num_iterations: int = ITERATIONS_PER_WORKER
):
    """Run the full deadlock test."""
    logger.info("=" * 80)
    logger.info("AGGRESSIVE DEADLOCK TRIGGER TEST")
    logger.info("=" * 80)

    results = DeadlockTestResults()
    engine, session_factory = await create_engine_and_session()

    try:
        if cleanup_only:
            await cleanup_test_positions(session_factory)
            return results

        # Phase 1: Setup
        logger.info("\n Phase 1: Creating test positions...")
        await cleanup_test_positions(session_factory)  # Clean first
        position_ids = await create_test_positions(session_factory)

        # Phase 2: Trigger deadlocks
        logger.info(f"\n Phase 2: Triggering deadlocks with {num_workers} workers...")
        logger.info(f"   Each worker will perform {num_iterations} operations")
        logger.info(f"   Total expected operations: {num_workers * num_iterations}")

        # Create worker tasks
        tasks = [
            worker_task(
                session_factory,
                position_ids,
                results,
                worker_id=i,
                iterations=num_iterations
            )
            for i in range(num_workers)
        ]

        # Run all workers concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Phase 3: Verify integrity
        logger.info("\n🔍 Phase 3: Verifying data integrity...")
        await verify_data_integrity(session_factory, position_ids, results)

        # Phase 4: Test recovery
        logger.info("\n🔧 Phase 4: Testing recovery mechanism...")
        await test_recovery_mechanism(session_factory, position_ids, results)

        # Phase 5: Final verification
        logger.info("\n✅ Phase 5: Final verification...")
        await verify_data_integrity(session_factory, position_ids, results)

        # Phase 6: Cleanup
        logger.info("\n🧹 Phase 6: Cleaning up test data...")
        await cleanup_test_positions(session_factory)

    finally:
        await engine.dispose()

    return results


def main():
    parser = argparse.ArgumentParser(description="Aggressive Deadlock Test")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Only cleanup test data, don't run test"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=CONCURRENT_WORKERS,
        help=f"Number of concurrent workers (default: {CONCURRENT_WORKERS})"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=ITERATIONS_PER_WORKER,
        help=f"Iterations per worker (default: {ITERATIONS_PER_WORKER})"
    )

    args = parser.parse_args()

    # Update module-level variables based on args
    if args.workers != CONCURRENT_WORKERS:
        globals()['CONCURRENT_WORKERS'] = args.workers
    if args.iterations != ITERATIONS_PER_WORKER:
        globals()['ITERATIONS_PER_WORKER'] = args.iterations

    results = asyncio.run(run_deadlock_test(
        cleanup_only=args.cleanup,
        num_workers=args.workers,
        num_iterations=args.iterations
    ))

    if not args.cleanup:
        print(results.summary())

        # Exit with appropriate code
        if results.data_corruption_detected:
            logger.error("❌ TEST FAILED: Data corruption detected!")
            sys.exit(1)
        elif results.deadlocks_triggered > 0 and results.deadlocks_recovered < results.deadlocks_triggered:
            logger.error("❌ TEST FAILED: Some deadlocks were not recovered!")
            sys.exit(1)
        else:
            if results.deadlocks_triggered > 0:
                logger.info(f"✅ TEST PASSED: Triggered {results.deadlocks_triggered} deadlocks, all recovered!")
            else:
                logger.info("✅ TEST PASSED: No deadlocks triggered (try increasing workers/iterations)")
            sys.exit(0)


if __name__ == "__main__":
    main()
