#!/usr/bin/env python3
"""
Comprehensive Test Monitoring Script
Monitors queue, positions, TP orders, and risk engine status
"""

import asyncio
import sys
from datetime import datetime
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path
sys.path.insert(0, '/app/backend')

from app.db.database import get_db_session as get_db
from app.models import (
    PositionGroup,
    DCAOrder,
    QueuedSignal,
    RiskAction,
    DCAConfiguration,
    Pyramid
)


async def monitor_pool_status(db: AsyncSession):
    """Monitor execution pool status"""
    print("=" * 60)
    print("   📊 EXECUTION POOL STATUS")
    print("=" * 60)

    # Count active positions
    result = await db.execute(
        select(func.count(PositionGroup.id))
        .where(PositionGroup.status.notin_(['closed', 'failed']))
    )
    active_count = result.scalar()

    # Count queued signals
    result = await db.execute(
        select(func.count(QueuedSignal.id))
        .where(QueuedSignal.status == 'queued')
    )
    queued_count = result.scalar()

    print(f"\n  Active Positions: {active_count}/10")
    print(f"  Queued Signals:   {queued_count}")
    print(f"  Pool Status:      {'🔴 FULL' if active_count >= 10 else '🟢 AVAILABLE'}")
    print()


async def monitor_positions_by_status(db: AsyncSession):
    """Monitor positions grouped by status"""
    print("=" * 60)
    print("   📈 POSITIONS BY STATUS")
    print("=" * 60)

    result = await db.execute(
        select(
            PositionGroup.status,
            func.count(PositionGroup.id).label('count')
        )
        .where(PositionGroup.status.notin_(['closed', 'failed']))
        .group_by(PositionGroup.status)
    )

    print(f"\n  {'Status':<20} {'Count':<10}")
    print(f"  {'-'*20} {'-'*10}")

    for row in result:
        print(f"  {row.status:<20} {row.count:<10}")
    print()


async def monitor_positions_pnl(db: AsyncSession):
    """Monitor positions by PnL"""
    print("=" * 60)
    print("   💰 POSITIONS BY PNL")
    print("=" * 60)

    result = await db.execute(
        select(
            PositionGroup.symbol,
            PositionGroup.exchange,
            PositionGroup.unrealized_pnl_percent,
            PositionGroup.unrealized_pnl_usd,
            PositionGroup.status
        )
        .where(PositionGroup.status.notin_(['closed', 'failed']))
        .order_by(PositionGroup.unrealized_pnl_percent.desc().nulls_last())
    )

    print(f"\n  {'Symbol':<12} {'Exchange':<10} {'PnL %':<10} {'PnL $':<12} {'Status':<15}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*12} {'-'*15}")

    for row in result:
        pnl_pct = f"{row.unrealized_pnl_percent:.2f}%" if row.unrealized_pnl_percent else "N/A"
        pnl_usd = f"${row.unrealized_pnl_usd:.2f}" if row.unrealized_pnl_usd else "N/A"

        # Color coding
        if row.unrealized_pnl_percent:
            if row.unrealized_pnl_percent > 0:
                pnl_pct = f"🟢 {pnl_pct}"
            else:
                pnl_pct = f"🔴 {pnl_pct}"

        print(f"  {row.symbol:<12} {row.exchange:<10} {pnl_pct:<10} {pnl_usd:<12} {row.status:<15}")
    print()


async def monitor_dca_orders(db: AsyncSession):
    """Monitor DCA order fill status"""
    print("=" * 60)
    print("   🎯 DCA ORDERS STATUS")
    print("=" * 60)

    result = await db.execute(
        select(
            DCAOrder.status,
            func.count(DCAOrder.id).label('count')
        )
        .group_by(DCAOrder.status)
    )

    print(f"\n  {'Status':<20} {'Count':<10}")
    print(f"  {'-'*20} {'-'*10}")

    for row in result:
        print(f"  {row.status:<20} {row.count:<10}")
    print()


async def monitor_tp_modes(db: AsyncSession):
    """Monitor TP modes configured"""
    print("=" * 60)
    print("   🎯 TAKE-PROFIT MODES")
    print("=" * 60)

    # Show TP modes configured
    print(f"\n  TP Modes Configured:")
    result = await db.execute(
        select(
            DCAConfiguration.tp_mode,
            func.count(DCAConfiguration.id).label('count')
        )
        .group_by(DCAConfiguration.tp_mode)
    )

    print(f"\n  {'TP Mode':<20} {'Count':<10}")
    print(f"  {'-'*20} {'-'*10}")

    for row in result:
        print(f"  {row.tp_mode:<20} {row.count:<10}")
    print()


async def monitor_queue(db: AsyncSession):
    """Monitor queue contents"""
    print("=" * 60)
    print("   📋 QUEUE CONTENTS")
    print("=" * 60)

    result = await db.execute(
        select(QueuedSignal)
        .where(QueuedSignal.status == 'queued')
        .order_by(QueuedSignal.priority_score.desc())
    )

    signals = result.scalars().all()

    if not signals:
        print("\n  ✅ Queue is empty")
    else:
        print(f"\n  Total Queued: {len(signals)}")
        print(f"\n  {'Symbol':<12} {'Exchange':<10} {'Priority':<10} {'Age (min)':<12} {'Replacements':<15}")
        print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*12} {'-'*15}")

        for signal in signals:
            age = (datetime.utcnow() - signal.queued_at).total_seconds() / 60
            priority = f"{signal.priority_score:.2f}" if signal.priority_score else "N/A"

            print(f"  {signal.symbol:<12} {signal.exchange:<10} {priority:<10} {age:<12.1f} {signal.replacement_count:<15}")
    print()


async def monitor_risk_engine(db: AsyncSession):
    """Monitor risk engine status"""
    print("=" * 60)
    print("   ⚠️  RISK ENGINE STATUS")
    print("=" * 60)

    # Count positions at risk
    result = await db.execute(
        select(func.count(PositionGroup.id))
        .where(PositionGroup.status.notin_(['closed', 'failed']))
        .where(PositionGroup.unrealized_pnl_percent < -2)
    )
    at_risk_count = result.scalar()

    print(f"\n  Positions at Risk (< -2%): {at_risk_count}")

    # Show positions with risk timer active
    result = await db.execute(
        select(
            PositionGroup.symbol,
            PositionGroup.exchange,
            PositionGroup.unrealized_pnl_percent,
            PositionGroup.risk_timer_start,
            PositionGroup.risk_eligible,
            PositionGroup.risk_blocked,
            PositionGroup.risk_skip_once
        )
        .where(PositionGroup.status.notin_(['closed', 'failed']))
        .where(PositionGroup.risk_timer_start.isnot(None))
        .order_by(PositionGroup.unrealized_pnl_percent.asc())
    )

    positions = result.all()

    if positions:
        print(f"\n  Positions with Active Risk Timer:")
        print(f"  {'Symbol':<12} {'Exchange':<10} {'PnL %':<10} {'Timer Start':<20} {'Eligible':<10} {'Blocked':<10}")
        print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*20} {'-'*10} {'-'*10}")

        for pos in positions:
            pnl = f"{pos.unrealized_pnl_percent:.2f}%" if pos.unrealized_pnl_percent else "N/A"
            timer = pos.risk_timer_start.strftime("%Y-%m-%d %H:%M:%S") if pos.risk_timer_start else "N/A"
            eligible = "Yes" if pos.risk_eligible else "No"
            blocked = "Yes" if pos.risk_blocked else "No"

            print(f"  {pos.symbol:<12} {pos.exchange:<10} {pnl:<10} {timer:<20} {eligible:<10} {blocked:<10}")

    # Recent risk actions
    result = await db.execute(
        select(RiskAction)
        .order_by(RiskAction.timestamp.desc())
        .limit(5)
    )

    actions = result.scalars().all()

    if actions:
        print(f"\n  Recent Risk Actions (Last 5):")
        print(f"  {'Action':<20} {'Notes':<30} {'Time':<20}")
        print(f"  {'-'*20} {'-'*30} {'-'*20}")

        for action in actions:
            time_str = action.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            notes = (action.notes[:27] + '...') if action.notes and len(action.notes) > 30 else (action.notes or 'N/A')

            print(f"  {action.action_type.value:<20} {notes:<30} {time_str:<20}")

    print()


async def monitor_order_types(db: AsyncSession):
    """Monitor order types distribution"""
    print("=" * 60)
    print("   📊 ORDER TYPE DISTRIBUTION")
    print("=" * 60)

    result = await db.execute(
        select(
            DCAConfiguration.entry_order_type,
            func.count(DCAConfiguration.id).label('count')
        )
        .group_by(DCAConfiguration.entry_order_type)
    )

    print(f"\n  {'Order Type':<20} {'Configurations':<15}")
    print(f"  {'-'*20} {'-'*15}")

    for row in result:
        print(f"  {row.entry_order_type:<20} {row.count:<15}")
    print()


async def main():
    """Main monitoring function"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "COMPREHENSIVE TEST MONITOR" + " " * 22 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    print(f"  🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    async for db in get_db():
        try:
            await monitor_pool_status(db)
            await monitor_positions_by_status(db)
            await monitor_positions_pnl(db)
            await monitor_dca_orders(db)
            await monitor_tp_modes(db)
            await monitor_queue(db)
            await monitor_risk_engine(db)
            await monitor_order_types(db)

            print("=" * 60)
            print("   ✅ Monitoring Complete")
            print("=" * 60)
            print()

        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break


if __name__ == "__main__":
    asyncio.run(main())
