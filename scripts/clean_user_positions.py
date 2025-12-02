import asyncio
import os
import sys
from sqlalchemy import select, delete

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup
from app.models.user import User
from app.models.dca_order import DCAOrder
from app.models.pyramid import Pyramid

async def clean_positions_for_user(username: str):
    async with AsyncSessionLocal() as session:
        # Get the user
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalars().first()

        if not user:
            print(f"User '{username}' not found.")
            return

        print(f"Found user: {user.username} ({user.id})")

        # First, get all group_ids for the user
        group_ids_result = await session.execute(
            select(PositionGroup.id).where(PositionGroup.user_id == user.id)
        )
        group_ids = group_ids_result.scalars().all()

        if group_ids:
            # Delete DCA orders associated with the user's position groups
            print(f"Deleting DCA orders associated with user's position groups...")
            await session.execute(delete(DCAOrder).where(DCAOrder.group_id.in_(group_ids)))
            await session.commit()
            print("DCA orders deleted.")

            # Delete Pyramid entries associated with the user's position groups
            print(f"Deleting Pyramid entries associated with user's position groups...")
            await session.execute(delete(Pyramid).where(Pyramid.group_id.in_(group_ids)))
            await session.commit()
            print("Pyramid entries deleted.")
        else:
            print("No position groups found for user.")

        # Delete position groups for the user
        print(f"Deleting position groups for user '{username}'...")
        await session.execute(delete(PositionGroup).where(PositionGroup.user_id == user.id))
        await session.commit()
        print("Position groups deleted.")
        
        print(f"All positions and associated orders for user '{username}' have been cleaned.")

if __name__ == "__main__":
    target_username = "zmomz"
    asyncio.run(clean_positions_for_user(target_username))
