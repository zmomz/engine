import asyncio
import os
import sys
import uuid

from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.models.position_group import PositionGroup # Import PositionGroup
from app.services.position_manager import PositionManagerService
from app.repositories.position_group import PositionGroupRepository
from app.services.grid_calculator import GridCalculatorService # Needed for PositionManagerService init
from app.services.order_management import OrderService # Needed for PositionManagerService init
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig # Needed for PositionManagerService init

async def trigger_update_position_stats(): # Removed user_id and position_group_id as arguments
    async with AsyncSessionLocal() as session:
        print(f"Triggering update_position_stats for all active PositionGroups...")
        
        # Get all active position groups
        position_group_repo = PositionGroupRepository(session)
        active_position_groups = await position_group_repo.get_active_position_groups()

        if not active_position_groups:
            print("No active position groups found to update.")
            return

        for position_group_obj in active_position_groups:
            # Fetch the user for each position group
            user = await session.get(User, position_group_obj.user_id)

            if not user:
                print(f"ERROR: User with ID {position_group_obj.user_id} not found for PositionGroup {position_group_obj.id}.")
                continue

            position_manager_service = PositionManagerService(
                session_factory=AsyncSessionLocal,
                user=user,
                position_group_repository_class=PositionGroupRepository,
                grid_calculator_service=GridCalculatorService(),
                order_service_class=OrderService
            )
            
            print(f"Updating stats for PositionGroup {position_group_obj.id} (Symbol: {position_group_obj.symbol})...")
            await position_manager_service.update_position_stats(position_group_obj.id, session=session)
            
            # Commit changes for each position group, or once after the loop
            # Let's commit inside the loop for now, to ensure each update is persisted.
            await session.commit() 
            print(f"Successfully triggered update_position_stats for PositionGroup {position_group_obj.id}.")

if __name__ == "__main__":
    asyncio.run(trigger_update_position_stats()) # No arguments needed now