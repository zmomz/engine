import asyncio
import os
import sys
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.dca_order import DCAOrder

async def inspect_orders():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DCAOrder))
        orders = result.scalars().all()
        for order in orders:
            print(f"Order ID: {order.id}")
            print(f"  Status: {order.status}")
            print(f"  Exchange ID: {order.exchange_order_id}")
            print(f"  TP Order ID: {order.tp_order_id}")
            print(f"  Filled Qty: {order.filled_quantity}")
            print("-" * 20)

if __name__ == "__main__":
    asyncio.run(inspect_orders())
