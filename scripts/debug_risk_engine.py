#!/usr/bin/env python
"""Debug script to check risk engine and position states."""
import asyncio
import sys
sys.path.insert(0, 'backend')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from datetime import datetime

async def check():
    engine = create_async_engine(settings.DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession)() as session:
        # Check positions
        result = await session.execute(text("""
            SELECT symbol, status, updated_at, risk_eligible, risk_timer_start,
                   risk_timer_expires, filled_dca_legs, total_dca_legs, pyramid_count,
                   total_filled_quantity, unrealized_pnl_percent
            FROM position_groups
            WHERE status IN ('active', 'closing', 'partially_filled')
            ORDER BY status, symbol
        """))
        rows = result.fetchall()

        print("=" * 80)
        print("POSITIONS IN DB:")
        print("=" * 80)
        now = datetime.utcnow()
        for r in rows:
            symbol, status, updated_at, risk_eligible, timer_start, timer_expires, filled, total, pyramids, qty, pnl = r
            time_in_status = (now - updated_at).total_seconds() if updated_at else 0
            print(f"\n{symbol}:")
            print(f"  status={status}, updated_at={updated_at} ({time_in_status:.0f}s ago)")
            print(f"  risk_eligible={risk_eligible}")
            print(f"  timer_start={timer_start}, timer_expires={timer_expires}")
            print(f"  filled_dca={filled}/{total}, pyramids={pyramids}")
            print(f"  qty={qty}, pnl%={pnl}")

        # Check Redis health for risk engine
        print("\n" + "=" * 80)
        print("CHECKING REDIS HEALTH:")
        print("=" * 80)
        try:
            from app.core.cache import get_cache
            cache = await get_cache()
            health = await cache.get_service_health("risk_engine")
            print(f"Risk Engine Health: {health}")

            ofm_health = await cache.get_service_health("order_fill_monitor")
            print(f"Order Fill Monitor Health: {ofm_health}")
        except Exception as e:
            print(f"Error checking Redis: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
