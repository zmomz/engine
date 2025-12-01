import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, delete

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.models.pyramid import Pyramid, PyramidStatus

async def setup_risk_scenario():
    async with AsyncSessionLocal() as session:
        # --- DOT (Loser) ---
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "DOTUSDT", PositionGroup.status == "live"))
        dot_group = result.scalars().first()
        
        if dot_group:
            print(f"Setting up DOT {dot_group.id} as LOSER...")
            # 1. Delete existing orders/pyramids
            await session.execute(delete(DCAOrder).where(DCAOrder.group_id == dot_group.id))
            await session.execute(delete(Pyramid).where(Pyramid.group_id == dot_group.id))
            
            # 2. Create 5 Pyramids
            for i in range(5):
                pyramid = Pyramid(
                    group_id=dot_group.id,
                    pyramid_index=i+1,
                    status=PyramidStatus.FILLED,
                    entry_price=Decimal("10.0"),
                    dca_config={}
                )
                session.add(pyramid)
                await session.flush()
                
                # Create Order for Pyramid
                order = DCAOrder(
                    group_id=dot_group.id,
                    pyramid_id=pyramid.id,
                    leg_index=0,
                    symbol="DOTUSDT",
                    side="buy",
                    order_type=OrderType.LIMIT,
                    price=Decimal("10.0"),
                    quantity=Decimal("20.0"), # 5 * 20 = 100
                    status=OrderStatus.FILLED.value,
                    filled_quantity=Decimal("20.0"),
                    avg_fill_price=Decimal("10.0"),
                    filled_at=datetime.utcnow(),
                    submitted_at=datetime.utcnow(),
                    exchange_order_id=f"fake_dot_{i}",
                    gap_percent=Decimal("0"),
                    weight_percent=Decimal("0"),
                    tp_percent=Decimal("0"),
                    tp_price=Decimal("0")
                )
                session.add(order)
            
            # 3. Update Group Stats
            dot_group.pyramid_count = 5
            dot_group.weighted_avg_entry = Decimal("10.0")
            dot_group.total_filled_quantity = Decimal("100.0")
            dot_group.total_invested_usd = Decimal("1000.0")
            dot_group.risk_timer_expires = datetime.utcnow() - timedelta(minutes=10)
            session.add(dot_group)
        else:
            print("DOT group not found")

        # --- ETH (Winner) ---
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "ETHUSDT", PositionGroup.status == "live"))
        eth_group = result.scalars().first()
        
        if eth_group:
            print(f"Setting up ETH {eth_group.id} as WINNER...")
            # 1. Delete existing orders/pyramids
            await session.execute(delete(DCAOrder).where(DCAOrder.group_id == eth_group.id))
            await session.execute(delete(Pyramid).where(Pyramid.group_id == eth_group.id))
            
            # 2. Create 1 Pyramid
            pyramid = Pyramid(
                group_id=eth_group.id,
                pyramid_index=1,
                status=PyramidStatus.FILLED,
                entry_price=Decimal("1000.0"),
                dca_config={}
            )
            session.add(pyramid)
            await session.flush()
            
            # Create Order
            order = DCAOrder(
                group_id=eth_group.id,
                pyramid_id=pyramid.id,
                leg_index=0,
                symbol="ETHUSDT",
                side="buy",
                order_type=OrderType.LIMIT,
                price=Decimal("1000.0"),
                quantity=Decimal("0.01"),
                status=OrderStatus.FILLED.value,
                filled_quantity=Decimal("0.01"),
                avg_fill_price=Decimal("1000.0"),
                filled_at=datetime.utcnow(),
                submitted_at=datetime.utcnow(),
                exchange_order_id="fake_eth_1",
                gap_percent=Decimal("0"),
                weight_percent=Decimal("0"),
                tp_percent=Decimal("0"),
                tp_price=Decimal("0")
            )
            session.add(order)
            
            # 3. Update Group Stats
            eth_group.pyramid_count = 1
            eth_group.weighted_avg_entry = Decimal("1000.0")
            eth_group.total_filled_quantity = Decimal("0.01")
            eth_group.total_invested_usd = Decimal("10.0")
            session.add(eth_group)
        else:
            print("ETH group not found")

        # --- SOLUSDT (Another Loser for diversity) ---
        result = await session.execute(select(PositionGroup).where(PositionGroup.symbol == "SOLUSDT", PositionGroup.status == "live"))
        sol_group = result.scalars().first()
        
        if sol_group:
            print(f"Setting up SOL {sol_group.id} as LOSER...")
            # 1. Delete existing orders/pyramids
            await session.execute(delete(DCAOrder).where(DCAOrder.group_id == sol_group.id))
            await session.execute(delete(Pyramid).where(Pyramid.group_id == sol_group.id))
            
            # 2. Create 5 Pyramids
            for i in range(5):
                pyramid = Pyramid(
                    group_id=sol_group.id,
                    pyramid_index=i+1,
                    status=PyramidStatus.FILLED,
                    entry_price=Decimal("150.0"), # High entry for current price ~125
                    dca_config={}
                )
                session.add(pyramid)
                await session.flush()
                
                # Create Order for Pyramid
                order = DCAOrder(
                    group_id=sol_group.id,
                    pyramid_id=pyramid.id,
                    leg_index=0,
                    symbol="SOLUSDT",
                    side="buy",
                    order_type=OrderType.LIMIT,
                    price=Decimal("150.0"),
                    quantity=Decimal("1.0"), 
                    status=OrderStatus.FILLED.value,
                    filled_quantity=Decimal("1.0"),
                    avg_fill_price=Decimal("150.0"),
                    filled_at=datetime.utcnow(),
                    submitted_at=datetime.utcnow(),
                    exchange_order_id=f"fake_sol_{i}",
                    gap_percent=Decimal("0"),
                    weight_percent=Decimal("0"),
                    tp_percent=Decimal("0"),
                    tp_price=Decimal("0")
                )
                session.add(order)
            
            # 3. Update Group Stats
            sol_group.pyramid_count = 5
            sol_group.weighted_avg_entry = Decimal("150.0")
            sol_group.total_filled_quantity = Decimal("5.0") # 5 pyramids * 1 SOL
            sol_group.total_invested_usd = Decimal("750.0") # 5 SOL * 150
            sol_group.risk_timer_expires = datetime.utcnow() - timedelta(minutes=10)
            session.add(sol_group)
        else:
            print("SOL group not found")
            
        await session.commit()
        print("Risk scenario v3 setup complete.")

if __name__ == "__main__":
    asyncio.run(setup_risk_scenario())
