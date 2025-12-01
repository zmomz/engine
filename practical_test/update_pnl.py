import asyncio
import os
import sys
from decimal import Decimal
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup

async def update_pnl():
    async with AsyncSessionLocal() as session:
        # XRP
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "XRPUSDT"))
        xrp_group = result.scalars().first()
        if xrp_group:
            print(f"Updating XRP PnL to -600")
            xrp_group.unrealized_pnl_usd = Decimal("-600.0")
            xrp_group.unrealized_pnl_percent = Decimal("-60.0")
            session.add(xrp_group)

        # ADA
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "ADAUSDT"))
        ada_group = result.scalars().first()
        if ada_group:
            print(f"Updating ADA PnL to +39000")
            ada_group.unrealized_pnl_usd = Decimal("39000.0")
            ada_group.unrealized_pnl_percent = Decimal("3900.0")
            session.add(ada_group)
            
        await session.commit()
        print("PnL updated.")

if __name__ == "__main__":
    asyncio.run(update_pnl())
