import asyncio
import os
import sys
from sqlalchemy import delete

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.queued_signal import QueuedSignal

async def clean_queue():
    async with AsyncSessionLocal() as session:
        print("Cleaning queue...")
        await session.execute(delete(QueuedSignal))
        await session.commit()
        print("Queue cleaned.")

if __name__ == "__main__":
    asyncio.run(clean_queue())
