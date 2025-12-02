"""
Check what orders exist in the database and their status
"""
import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup
from app.models.user import User

async def check_order_status():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        user_id = "977c8888-b704-43e1-a5ab-0aeec8558a21"
        
        # Get position groups
        result = await session.execute(select(PositionGroup).where(PositionGroup.user_id == user_id))
        groups = result.scalars().all()
        
        if not groups:
            print("No position groups found")
            return
        
        print(f"Found {len(groups)} position groups:")
        for group in groups:
            print(f"\nGroup: {group.id}")
            print(f"  Symbol: {group.symbol}")
            print(f"  Side: {group.side}")
            print(f"  Status: {group.status}")
            print(f"  Total filled qty: {group.total_filled_quantity}")
            
            # Get orders for this group
            result = await session.execute(
                select(DCAOrder)
                .where(DCAOrder.group_id == group.id)
                .order_by(DCAOrder.created_at.desc())
            )
            orders = result.scalars().all()
            
            print(f"  Orders: {len(orders)}")
            for order in orders:
                print(f"    - Order {order.id}")
                print(f"      Exchange ID: {order.exchange_order_id}")
                print(f"      Status: {order.status}")
                print(f"      Price: {order.price}")
                print(f"      Quantity: {order.quantity}")
                print(f"      Filled: {order.filled_quantity}")
                print(f"      Created: {order.created_at}")
                print(f"      Submitted: {order.submitted_at}")
                print(f"      Filled at: {order.filled_at}")
                print(f"      Cancelled at: {order.cancelled_at}")

if __name__ == "__main__":
    asyncio.run(check_order_status())
