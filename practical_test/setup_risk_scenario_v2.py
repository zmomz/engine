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
        # Find DOTUSDT (Loser)
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "DOTUSDT", PositionGroup.status == "live"))
        dot_group = result.scalars().first()
        
        if dot_group:
            print(f"Updating DOT {dot_group.id} to be LOSER")
            # Current price ~2.1. Set entry to 10.0
            dot_group.weighted_avg_entry = Decimal("10.0") 
            dot_group.pyramid_count = 5
            # Status needs to be ACTIVE or LIVE? Risk engine checks for...
            # Usually 'ACTIVE' means all DCA filled.
            # But 'LIVE' is fine if timer is set.
            # Risk engine condition: 
            # 1. 5 pyramids (if config says so)
            # 2. Timer expired.
            
            dot_group.risk_timer_expires = datetime.utcnow() - timedelta(minutes=10) # Expired
            
            # Set total_invested_usd to allow partial close calculation
            # Assume we have some size
            dot_group.total_invested_usd = Decimal("1000.0")
            dot_group.total_filled_quantity = Decimal("100.0") # 1000 / 10 = 100 DOT
            
            # Update unrealized PnL to simulate loss (for display/debugging, though risk engine re-calcs)
            # 2.1 - 10 = -7.9 per DOT. * 100 = -790 USD.
            # -790 / 1000 = -79%.
            
            session.add(dot_group)
        else:
            print("DOT group not found")

        # Find ETHUSDT (Winner)
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "ETHUSDT", PositionGroup.status == "live"))
        eth_group = result.scalars().first()
        
        if eth_group:
            print(f"Updating ETH {eth_group.id} to be WINNER")
            # Current price ~3400. Set entry to 1000.
            eth_group.weighted_avg_entry = Decimal("1000.0") 
            
            eth_group.total_invested_usd = Decimal("10.0") # 0.01 * 1000
            eth_group.total_filled_quantity = Decimal("0.01") # Match actual testnet size
            
            session.add(eth_group)
        else:
            print("ETH group not found")
            
        await session.commit()
        print("Risk scenario setup complete.")

if __name__ == "__main__":
    asyncio.run(setup_risk_scenario())
