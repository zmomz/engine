import asyncio
import os
import sys
import logging
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.services.risk_engine import RiskEngineService
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.order_management import OrderService
from app.schemas.grid_config import RiskEngineConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def trigger_risk():
    async with AsyncSessionLocal() as session:
        # Get user
        result = await session.execute(select(User).where(User.username == "maaz"))
        user = result.scalars().first()
        
        if not user:
            print("User not found")
            return

        # Config
        try:
            risk_config = RiskEngineConfig(**user.risk_config)
        except:
            risk_config = RiskEngineConfig()
            
        async def session_factory():
            yield session

        service = RiskEngineService(
            session_factory=session_factory,
            position_group_repository_class=PositionGroupRepository,
            risk_action_repository_class=RiskActionRepository,
            dca_order_repository_class=DCAOrderRepository,
            order_service_class=OrderService,
            risk_engine_config=risk_config,
            user=user
        )
        
        print("Running risk evaluation...")
        await service.run_single_evaluation()
        print("Risk evaluation finished.")

if __name__ == "__main__":
    asyncio.run(trigger_risk())
