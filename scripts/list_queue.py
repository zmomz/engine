import asyncio
import os
import sys
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.queued_signal import QueuedSignal

async def list_queue():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(QueuedSignal))
        signals = result.scalars().all()
        print(f"Total Queued Signals: {len(signals)}")
        for s in signals:
            print(f"ID: {s.id}")
            print(f"  Symbol: {s.symbol}")
            print(f"  Timeframe: {s.timeframe}")
            print(f"  Side: {s.side}")
            print(f"  Status: {s.status}")
            print(f"  Entry: {s.entry_price}")
            print(f"  Replacement Count: {s.replacement_count}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(list_queue())
