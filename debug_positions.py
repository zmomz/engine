import asyncio
import os
import sys
from sqlalchemy import select
from decimal import Decimal

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup
from app.models.user import User
from app.models.dca_order import DCAOrder

async def main():
    async with AsyncSessionLocal() as session:
        # Get users
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f"Found {len(users)} users.")
        
        for user in users:
            print(f"User: {user.username} ({user.id})")
            
            # Get ALL positions
            result = await session.execute(
                select(PositionGroup).where(
                    PositionGroup.user_id == user.id
                )
            )
            groups = result.scalars().all()
            print(f"  Total Groups: {len(groups)}")
            
            for g in groups:
                print(f"    Group {g.id}: Symbol={g.symbol}, Status={g.status}")
                print(f"      Total Filled Qty: {g.total_filled_quantity}")
                print(f"      Avg Entry: {g.weighted_avg_entry}")
                
                # Check orders directly
                result_orders = await session.execute(
                    select(DCAOrder).where(DCAOrder.group_id == g.id)
                )
                orders = result_orders.scalars().all()
                print(f"      Orders (Direct Query): {len(orders)}")
                for o in orders:
                    print(f"        Order {o.leg_index}: Status={o.status}, Filled={o.filled_quantity}, Price={o.price}")

if __name__ == "__main__":
    asyncio.run(main())
