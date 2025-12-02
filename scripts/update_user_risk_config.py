import asyncio
import sys
import os
from decimal import Decimal
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.schemas.grid_config import RiskEngineConfig # Import the schema for validation

async def update_user_risk_config(user_id: str, new_max_exposure: str):
    async with AsyncSessionLocal() as session:
        user_uuid = uuid.UUID(user_id)
        result = await session.execute(select(User).filter(User.id == user_uuid))
        user = result.scalar_one_or_none()

        if user:
            print(f"Found user: {user.username}")
            current_risk_config = RiskEngineConfig(**user.risk_config)
            print(f"Current max_total_exposure_usd: {current_risk_config.max_total_exposure_usd}")

            current_risk_config.max_total_exposure_usd = Decimal(new_max_exposure)
            user.risk_config = current_risk_config.model_dump(mode='json')

            session.add(user)
            await session.commit()
            print(f"Updated user {user.username}'s max_total_exposure_usd to: {user.risk_config['max_total_exposure_usd']}")
        else:
            print(f"User with ID {user_id} not found.")

if __name__ == "__main__":
    # Get user ID from the test plan
    test_user_id = "c788bbcd-57e7-42f7-aa06-870a8dfc994f"
    
    # New max_total_exposure_usd value
    new_exposure = "1000" # Increased to ensure notional > 100

    asyncio.run(update_user_risk_config(test_user_id, new_exposure))
