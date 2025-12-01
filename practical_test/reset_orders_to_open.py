import asyncio
import os
import sys
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.dca_order import DCAOrder, OrderStatus

async def reset_orders():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DCAOrder).where(DCAOrder.status == "filled"))
        orders = result.scalars().all()
        for order in orders:
            print(f"Resetting Order ID: {order.id} to open")
            order.status = OrderStatus.OPEN.value
            session.add(order)
        await session.commit()
        print("Orders reset.")

if __name__ == "__main__":
    asyncio.run(reset_orders())
