import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from app.db.database import AsyncSessionLocal
from app.repositories.position_group import PositionGroupRepository
from app.models.user import User
from app.models.position_group import PositionGroup
from sqlalchemy import select, delete

async def clear_positions():
    async with AsyncSessionLocal() as session:
        # Find zmomz
        result = await session.execute(select(User).where(User.username == "zmomz"))
        user = result.scalar_one_or_none()
        if not user:
            print("User zmomz not found")
            return

        # Delete all position groups for zmomz
        from sqlalchemy.orm import selectinload # Import selectinload
        result = await session.execute(select(PositionGroup)
                                       .where(PositionGroup.user_id == user.id)
                                       .options(selectinload(PositionGroup.pyramids), selectinload(PositionGroup.dca_orders)))
        groups_to_delete = result.scalars().all()
        
        for group in groups_to_delete:
            await session.delete(group)
        
        await session.commit()
        print(f"All position groups for user {user.username} (ID: {user.id}) cleared.")

if __name__ == "__main__":
    asyncio.run(clear_positions())
