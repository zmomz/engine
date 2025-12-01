import asyncio
import os
import sys
import uuid
import argparse
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.dca_order import DCAOrder

async def inspect_orders(group_id: str = None):
    async with AsyncSessionLocal() as session:
        if group_id:
            stmt = select(DCAOrder).where(DCAOrder.group_id == uuid.UUID(group_id))
        else:
            stmt = select(DCAOrder)
        
        result = await session.execute(stmt)
        orders = result.scalars().all()
        
        print(f"Total Orders: {len(orders)}")
        for order in orders:
            print(f"Order ID: {order.id}")
            print(f"  Group ID: {order.group_id}")
            print(f"  Pyramid ID: {order.pyramid_id}")
            print(f"  Leg Index: {order.leg_index}")
            print(f"  Status: {order.status}")
            print(f"  Exchange ID: {order.exchange_order_id}")
            print(f"  TP Order ID: {order.tp_order_id}")
            print(f"  Filled Qty: {order.filled_quantity}")
            print("-" * 20)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect DCA orders in the database.")
    parser.add_argument('--group-id', type=str, help='Optional: Filter orders by PositionGroup ID.')
    args = parser.parse_args()
    
    asyncio.run(inspect_orders(group_id=args.group_id))
