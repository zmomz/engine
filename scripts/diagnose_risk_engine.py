#!/usr/bin/env python
"""
Diagnose Risk Engine Issues

This script checks:
1. Current position states in the database
2. Recent risk engine activity
3. Any stuck positions

Usage:
    python scripts/diagnose_risk_engine.py
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime, timedelta

async def diagnose():
    """Run diagnostics on the risk engine."""
    from app.core.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession)() as session:
        print("=" * 70)
        print("RISK ENGINE DIAGNOSTICS")
        print("=" * 70)
        now = datetime.utcnow()

        # 1. Check all active and closing positions
        print("\n📊 POSITION STATUS:")
        print("-" * 70)
        result = await session.execute(text("""
            SELECT
                symbol,
                status,
                filled_dca_legs,
                total_dca_legs,
                pyramid_count,
                risk_eligible,
                risk_timer_start,
                risk_timer_expires,
                updated_at,
                unrealized_pnl_percent,
                total_filled_quantity
            FROM position_groups
            WHERE status IN ('active', 'closing', 'partially_filled', 'live')
            ORDER BY status, symbol
        """))
        rows = result.fetchall()

        if not rows:
            print("No active positions found.")
        else:
            for row in rows:
                symbol, status, filled, total, pyramids, eligible, timer_start, timer_expires, updated_at, pnl_pct, qty = row
                time_since_update = (now - updated_at).total_seconds() if updated_at else 0

                status_emoji = {
                    'active': '🟢',
                    'closing': '🟡',
                    'partially_filled': '🔵',
                    'live': '⚪'
                }.get(status, '❓')

                timer_info = ""
                if timer_expires:
                    if now >= timer_expires:
                        timer_info = "⏰ EXPIRED"
                    else:
                        remaining = (timer_expires - now).total_seconds()
                        timer_info = f"⏳ {remaining:.0f}s left"

                print(f"\n{status_emoji} {symbol}")
                print(f"   Status: {status}")
                print(f"   DCA: {filled}/{total}, Pyramids: {pyramids}")
                print(f"   PnL: {pnl_pct:.2f}%, Qty: {qty}")
                print(f"   Risk Eligible: {eligible}")
                print(f"   Timer: {timer_info}")
                print(f"   Updated: {time_since_update:.0f}s ago")

        # 2. Check for stuck CLOSING positions
        print("\n" + "=" * 70)
        print("⚠️ STUCK CLOSING POSITIONS:")
        print("-" * 70)
        result = await session.execute(text("""
            SELECT symbol, updated_at, total_filled_quantity
            FROM position_groups
            WHERE status = 'closing'
        """))
        closing_rows = result.fetchall()

        if not closing_rows:
            print("No positions in CLOSING status - good!")
        else:
            for row in closing_rows:
                symbol, updated_at, qty = row
                time_in_closing = (now - updated_at).total_seconds() if updated_at else 0
                print(f"   {symbol}: in CLOSING for {time_in_closing:.0f}s, qty={qty}")
                if time_in_closing > 120:  # > 2 minutes
                    print(f"      ⚠️ STUCK! Should have been recovered by now")

        # 3. Check recent risk actions
        print("\n" + "=" * 70)
        print("📋 RECENT RISK ACTIONS:")
        print("-" * 70)
        result = await session.execute(text("""
            SELECT
                ra.timestamp,
                ra.action_type,
                pg.symbol as loser_symbol,
                ra.loser_pnl_usd,
                ra.notes
            FROM risk_actions ra
            LEFT JOIN position_groups pg ON ra.loser_group_id = pg.id
            ORDER BY ra.timestamp DESC
            LIMIT 5
        """))
        action_rows = result.fetchall()

        if not action_rows:
            print("No recent risk actions found.")
        else:
            for row in action_rows:
                ts, action_type, symbol, pnl, notes = row
                print(f"   {ts}: {action_type} - {symbol} (${pnl:.2f})")
                if notes:
                    print(f"      Notes: {notes}")

        # 4. Summary and recommendations
        print("\n" + "=" * 70)
        print("💡 RECOMMENDATIONS:")
        print("-" * 70)

        closing_count = len(closing_rows) if closing_rows else 0
        if closing_count > 0:
            print(f"   • {closing_count} position(s) stuck in CLOSING - run fix script or wait for auto-recovery")

        # Check for positions that should be eligible but aren't
        eligible_losers = [r for r in rows if r[5] and r[9] < -1.5]  # risk_eligible=True and pnl < -1.5%
        if eligible_losers:
            print(f"   • {len(eligible_losers)} position(s) are risk-eligible losers")

        profitable = [r for r in rows if r[9] > 0]
        if profitable:
            print(f"   • {len(profitable)} position(s) are profitable (potential winners)")

        if not eligible_losers and not profitable:
            print("   • No offset opportunities currently available")

        print("\n" + "=" * 70)
        print("To view live logs, run:")
        print("   docker logs -f <backend-container-name> 2>&1 | grep -i 'risk engine'")
        print("=" * 70)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(diagnose())
