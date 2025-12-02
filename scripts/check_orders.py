import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings
from app.models.dca_order import DCAOrder
from app.models.user import User

async def check_orders(user_id):
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get user
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if not user:
            print(f"User {user_id} not found")
            return

        print(f"Checking orders for user {user.username} ({user.id})...")
        
        # Get orders
        # Join with PositionGroup to filter by user_id via group relationship if needed, 
        # but DCAOrder doesn't have user_id directly. It's linked via PositionGroup.
        # Let's fetch PositionGroups for the user first.
        from app.models.position_group import PositionGroup
        
        result = await session.execute(select(PositionGroup).where(PositionGroup.user_id == user_id))
        groups = result.scalars().all()
        group_ids = [g.id for g in groups]
        
        if not group_ids:
            print("No position groups found for user.")
            return

        result = await session.execute(select(DCAOrder).where(DCAOrder.group_id.in_(group_ids)).order_by(DCAOrder.created_at.desc()).limit(10))
        orders = result.scalars().all()
        
        if not orders:
            print("No orders found.")
        else:
            for order in orders:
                print(f"Order {order.id}: Exchange ID={order.exchange_order_id}, Status={order.status}, Symbol={order.symbol}, Created={order.created_at}")

if __name__ == "__main__":
    user_id = "977c8888-b704-43e1-a5ab-0aeec8558a21"
    asyncio.run(check_orders(user_id))
