import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup, PositionGroupStatus

async def setup_risk_scenario():
    async with AsyncSessionLocal() as session:
        # Find XRP (Loser)
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "XRPUSDT", PositionGroup.status == "live"))
        xrp_group = result.scalars().first()
        
        if xrp_group:
            print(f"Updating XRP {xrp_group.id} to be LOSER")
            xrp_group.weighted_avg_entry = Decimal("5.0") # High entry for Long -> Loss
            xrp_group.pyramid_count = 5
            xrp_group.status = PositionGroupStatus.ACTIVE # Fully filled
            xrp_group.risk_timer_expires = datetime.utcnow() - timedelta(minutes=10) # Expired
            # Set total_invested_usd to allow partial close calculation
            xrp_group.total_invested_usd = Decimal("1000.0")
            xrp_group.total_filled_quantity = Decimal("200.0") # 1000 / 5 = 200
            session.add(xrp_group)
        else:
            print("XRP group not found")

        # Find ADA (Winner)
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "ADAUSDT", PositionGroup.status == "live"))
        ada_group = result.scalars().first()
        
        if ada_group:
            print(f"Updating ADA {ada_group.id} to be WINNER")
            ada_group.weighted_avg_entry = Decimal("0.01") # Low entry for Long -> Profit
            # Keep status live
            ada_group.total_invested_usd = Decimal("1000.0")
            ada_group.total_filled_quantity = Decimal("100000.0") # 1000 / 0.01
            session.add(ada_group)
        else:
            print("ADA group not found")
            
        await session.commit()
        print("Risk scenario setup complete.")

if __name__ == "__main__":
    asyncio.run(setup_risk_scenario())
