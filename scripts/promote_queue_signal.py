#!/usr/bin/env python3
"""
Manually promote a signal from the queue
This script simulates what an automatic queue processor would do
"""

import asyncio
import sys
import uuid

sys.path.insert(0, '/app/backend')

from app.db.database import get_db_session as get_db
from app.services.queue_manager import QueueManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.models.user import User
from sqlalchemy import select


async def promote_highest_priority_signal():
    """Promote the signal with highest priority score"""
    print("\n" + "=" * 70)
    print("  QUEUE PROMOTION - Highest Priority")
    print("=" * 70)
    print()

    async for db in get_db():
        try:
            # Get user
            result = await db.execute(
                select(User).where(User.username == "zmomz")
            )
            user = result.scalar_one_or_none()
            if not user:
                print("❌ User 'zmomz' not found")
                return

            # Initialize services
            queue_repo = QueuedSignalRepository(db)
            pos_repo = PositionGroupRepository(db)

            # Get all queued signals
            signals = await queue_repo.get_all_queued_signals_for_user(str(user.id))
            if not signals:
                print("✅ Queue is empty - nothing to promote")
                return

            # Get active positions for priority calculation
            active_groups = await pos_repo.get_active_position_groups_for_user(user.id)

            print(f"Found {len(signals)} queued signals")
            print(f"Active positions: {len(active_groups)}/10")
            print()

            # Calculate priority for each signal
            from app.services.queue_priority import calculate_queue_priority, explain_priority
            from app.schemas.grid_config import PriorityRulesConfig

            # Load user's priority config
            priority_config = PriorityRulesConfig()  # Use default for now

            signal_priorities = []
            for signal in signals:
                priority_score = calculate_queue_priority(signal, active_groups, priority_config)
                explanation = explain_priority(signal, active_groups, priority_config)
                signal_priorities.append((signal, priority_score, explanation))

            # Sort by priority (highest first)
            signal_priorities.sort(key=lambda x: x[1], reverse=True)

            print("Queue Priority Order:")
            print(f"{'Rank':<6} {'Symbol':<12} {'Priority':<15} {'Explanation'}")
            print("-" * 70)
            for i, (signal, score, explanation) in enumerate(signal_priorities, 1):
                print(f"{i:<6} {signal.symbol:<12} {score:<15} {explanation}")

            print()
            print(f"Highest priority signal: {signal_priorities[0][0].symbol}")
            print(f"Priority score: {signal_priorities[0][1]}")
            print(f"Explanation: {signal_priorities[0][2]}")
            print()

            # Check if pool has space
            active_count = len(active_groups)
            if active_count >= 10:
                print(f"❌ Pool is full ({active_count}/10) - cannot promote")
                return

            print(f"✅ Pool has space ({active_count}/10)")
            print()

            # Promote the highest priority signal
            highest_priority_signal = signal_priorities[0][0]

            print(f"Promoting {highest_priority_signal.symbol}...")

            # Create queue manager service
            def get_session():
                return get_db()

            pool_manager = ExecutionPoolManager(
                session_factory=get_session,
                position_group_repository_class=PositionGroupRepository
            )

            queue_manager = QueueManagerService(
                session_factory=get_session,
                user=user,
                execution_pool_manager=pool_manager
            )

            # Promote the signal
            promoted = await queue_manager.promote_specific_signal(
                highest_priority_signal.id,
                user_id=user.id
            )

            if promoted:
                print(f"✅ Successfully promoted {highest_priority_signal.symbol}")
                print(f"   Status changed to: {promoted.status}")
                print(f"   Promoted at: {promoted.promoted_at}")
            else:
                print(f"❌ Failed to promote {highest_priority_signal.symbol}")
                print("   Possible reasons:")
                print("   - Pool is full")
                print("   - Signal no longer exists")
                print("   - Execution failed")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break

    print()
    print("=" * 70)


async def main():
    await promote_highest_priority_signal()


if __name__ == "__main__":
    asyncio.run(main())
