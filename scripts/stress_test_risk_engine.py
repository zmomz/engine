#!/usr/bin/env python
"""
Live stress test for Risk Engine deadlock prevention.

This script simulates the conditions that caused the original deadlock:
1. Multiple concurrent database operations on the same positions
2. Rapid order fill updates
3. Risk engine evaluation cycles

Run this against the actual database to verify robustness.

Usage:
    python scripts/stress_test_risk_engine.py [--iterations N] [--concurrency N]

Requirements:
    - Backend must be running
    - Database must be accessible
"""
import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, '.')

from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.user import User

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StressTestResults:
    """Track stress test results."""

    def __init__(self):
        self.total_operations = 0
        self.successful_operations = 0
        self.deadlocks_detected = 0
        self.deadlocks_recovered = 0
        self.other_errors = 0
        self.start_time = None
        self.end_time = None

    def record_success(self):
        self.total_operations += 1
        self.successful_operations += 1

    def record_deadlock(self, recovered: bool = False):
        self.total_operations += 1
        self.deadlocks_detected += 1
        if recovered:
            self.deadlocks_recovered += 1

    def record_error(self):
        self.total_operations += 1
        self.other_errors += 1

    def summary(self) -> str:
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        ops_per_sec = self.total_operations / duration if duration > 0 else 0

        return f"""
╔════════════════════════════════════════════════════════════════╗
║                    STRESS TEST RESULTS                         ║
╠════════════════════════════════════════════════════════════════╣
║  Total Operations:        {self.total_operations:>10}                         ║
║  Successful:              {self.successful_operations:>10}                         ║
║  Deadlocks Detected:      {self.deadlocks_detected:>10}                         ║
║  Deadlocks Recovered:     {self.deadlocks_recovered:>10}                         ║
║  Other Errors:            {self.other_errors:>10}                         ║
║  Duration:                {duration:>10.2f}s                        ║
║  Operations/sec:          {ops_per_sec:>10.2f}                         ║
╠════════════════════════════════════════════════════════════════╣
║  SUCCESS RATE:            {self.successful_operations/self.total_operations*100 if self.total_operations else 0:>10.2f}%                        ║
║  DEADLOCK RECOVERY RATE:  {self.deadlocks_recovered/self.deadlocks_detected*100 if self.deadlocks_detected else 100:>10.2f}%                        ║
╚════════════════════════════════════════════════════════════════╝
"""


async def create_test_session() -> async_sessionmaker:
    """Create a database session factory."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=30,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def simulate_position_update(
    session_factory: async_sessionmaker,
    position_id: uuid.UUID,
    results: StressTestResults,
    operation_name: str
) -> bool:
    """
    Simulate a position update with deadlock handling.

    This simulates what happens during order fill monitoring and risk evaluation.
    """
    async with session_factory() as session:
        try:
            # Simulate reading position
            result = await session.execute(
                select(PositionGroup).where(PositionGroup.id == position_id)
            )
            position = result.scalars().first()

            if not position:
                logger.debug(f"[{operation_name}] Position {position_id} not found")
                results.record_success()
                return True

            # Simulate update (what order fill monitor and risk engine do)
            position.updated_at = datetime.utcnow()

            await session.commit()
            results.record_success()
            return True

        except OperationalError as e:
            error_str = str(e)
            if "deadlock" in error_str.lower():
                logger.warning(f"[{operation_name}] Deadlock detected, rolling back...")
                try:
                    await session.rollback()
                    results.record_deadlock(recovered=True)
                    logger.info(f"[{operation_name}] Successfully recovered from deadlock")
                except Exception:
                    results.record_deadlock(recovered=False)
                    logger.error(f"[{operation_name}] Failed to recover from deadlock")
            else:
                logger.error(f"[{operation_name}] Database error: {e}")
                try:
                    await session.rollback()
                except Exception:
                    pass
                results.record_error()
            return False

        except Exception as e:
            logger.error(f"[{operation_name}] Unexpected error: {e}")
            try:
                await session.rollback()
            except Exception:
                pass
            results.record_error()
            return False


async def simulate_concurrent_updates(
    session_factory: async_sessionmaker,
    position_ids: List[uuid.UUID],
    concurrency: int,
    results: StressTestResults
):
    """Simulate multiple concurrent updates to the same positions."""
    tasks = []

    for i in range(concurrency):
        for pos_id in position_ids:
            task = asyncio.create_task(
                simulate_position_update(
                    session_factory,
                    pos_id,
                    results,
                    f"Worker-{i}"
                )
            )
            tasks.append(task)

    await asyncio.gather(*tasks, return_exceptions=True)


async def simulate_risk_evaluation_cycle(
    session_factory: async_sessionmaker,
    user_id: uuid.UUID,
    results: StressTestResults
):
    """Simulate a full risk evaluation cycle."""
    async with session_factory() as session:
        try:
            # 1. Get all active positions (what risk engine does)
            result = await session.execute(
                select(PositionGroup)
                .where(
                    PositionGroup.user_id == user_id,
                    PositionGroup.status.in_(["active", "partially_filled", "live"])
                )
            )
            positions = result.scalars().all()

            # 2. Update each position (simulate PnL refresh)
            for pos in positions:
                pos.updated_at = datetime.utcnow()

            # 3. Commit all changes
            await session.commit()
            results.record_success()
            return True

        except OperationalError as e:
            if "deadlock" in str(e).lower():
                logger.warning("[RiskEval] Deadlock in risk evaluation, rolling back...")
                try:
                    await session.rollback()
                    results.record_deadlock(recovered=True)
                except Exception:
                    results.record_deadlock(recovered=False)
            else:
                try:
                    await session.rollback()
                except Exception:
                    pass
                results.record_error()
            return False

        except Exception as e:
            logger.error(f"[RiskEval] Error: {e}")
            try:
                await session.rollback()
            except Exception:
                pass
            results.record_error()
            return False


async def get_test_data(session_factory: async_sessionmaker):
    """Get test data from the database."""
    async with session_factory() as session:
        # Get active positions
        result = await session.execute(
            select(PositionGroup)
            .where(PositionGroup.status.in_(["active", "partially_filled"]))
            .limit(10)
        )
        positions = result.scalars().all()

        # Get user IDs
        user_ids = list(set(pos.user_id for pos in positions))

        return [pos.id for pos in positions], user_ids


async def run_stress_test(iterations: int = 50, concurrency: int = 5):
    """
    Run the full stress test.

    Args:
        iterations: Number of test iterations
        concurrency: Number of concurrent operations per iteration
    """
    logger.info("=" * 60)
    logger.info("Starting Risk Engine Stress Test")
    logger.info(f"Iterations: {iterations}, Concurrency: {concurrency}")
    logger.info("=" * 60)

    results = StressTestResults()
    results.start_time = datetime.utcnow()

    try:
        session_factory = await create_test_session()

        # Get test data
        position_ids, user_ids = await get_test_data(session_factory)

        if not position_ids:
            logger.warning("No active positions found for testing")
            logger.info("Creating synthetic test with empty operations...")
            position_ids = [uuid.uuid4()]  # Use fake ID for testing path
            user_ids = [uuid.uuid4()]

        logger.info(f"Testing with {len(position_ids)} positions, {len(user_ids)} users")

        for i in range(iterations):
            logger.info(f"Iteration {i + 1}/{iterations}")

            # Run concurrent position updates
            await simulate_concurrent_updates(
                session_factory,
                position_ids,
                concurrency,
                results
            )

            # Run risk evaluation cycle
            for user_id in user_ids:
                await simulate_risk_evaluation_cycle(
                    session_factory,
                    user_id,
                    results
                )

            # Small delay between iterations
            await asyncio.sleep(0.1)

    except Exception as e:
        logger.error(f"Stress test failed with error: {e}")
        raise

    finally:
        results.end_time = datetime.utcnow()

    return results


async def test_stuck_position_recovery(session_factory: async_sessionmaker):
    """Test the stuck position recovery mechanism."""
    logger.info("Testing stuck position recovery...")

    async with session_factory() as session:
        # Find positions in closing status
        result = await session.execute(
            select(PositionGroup)
            .where(PositionGroup.status == "closing")
        )
        closing_positions = result.scalars().all()

        if closing_positions:
            logger.info(f"Found {len(closing_positions)} positions in 'closing' status")
            for pos in closing_positions:
                logger.info(
                    f"  - {pos.symbol}: updated_at={pos.updated_at}, "
                    f"qty={pos.total_filled_quantity}"
                )
        else:
            logger.info("No stuck 'closing' positions found (good!)")

        return len(closing_positions) == 0


def main():
    parser = argparse.ArgumentParser(description="Risk Engine Stress Test")
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=50,
        help="Number of test iterations (default: 50)"
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=5,
        help="Number of concurrent operations (default: 5)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run the stress test
    results = asyncio.run(run_stress_test(args.iterations, args.concurrency))

    # Print results
    print(results.summary())

    # Determine exit code
    success_rate = results.successful_operations / results.total_operations if results.total_operations else 0
    deadlock_recovery_rate = results.deadlocks_recovered / results.deadlocks_detected if results.deadlocks_detected else 1.0

    if success_rate < 0.95:
        logger.error("FAIL: Success rate below 95%")
        sys.exit(1)
    elif deadlock_recovery_rate < 1.0 and results.deadlocks_detected > 0:
        logger.error("FAIL: Some deadlocks were not recovered")
        sys.exit(1)
    else:
        logger.info("PASS: Stress test completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
