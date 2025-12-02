import asyncio
import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, and_
import argparse # Added this import

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.models.user import User
from app.models.position_group import PositionGroup
from app.services.position_manager import PositionManagerService
from app.repositories.position_group import PositionGroupRepository
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService

async def simulate_tp_closure(position_group_id: str, dca_order_id_to_close: str):
    async with AsyncSessionLocal() as session:
        pg_uuid = uuid.UUID(position_group_id)
        dca_uuid_to_close = uuid.UUID(dca_order_id_to_close)
        
        # 1. Fetch the PositionGroup
        result = await session.execute(select(PositionGroup).where(PositionGroup.id == pg_uuid))
        position_group = result.scalars().first()
        
        if not position_group:
            print(f"PositionGroup with ID {position_group_id} not found.")
            return

        # 2. Fetch the specific DCA order to simulate TP closure (the entry leg)
        result = await session.execute(
            select(DCAOrder).where(
                and_(
                    DCAOrder.group_id == pg_uuid,
                    DCAOrder.id == dca_uuid_to_close,
                    DCAOrder.status == OrderStatus.FILLED # Only close filled entry orders
                )
            )
        )
        dca_entry_order = result.scalars().first()

        if not dca_entry_order:
            print(f"No FILLED DCA entry order found with ID {dca_order_id_to_close} for PositionGroup {position_group_id}.")
            return

        print(f"Simulating TP closure for DCA Entry Order ID: {dca_entry_order.id}")
        
        # 3. Mark the entry order as TP hit
        dca_entry_order.tp_hit = True
        dca_entry_order.tp_executed_at = datetime.utcnow()
        session.add(dca_entry_order)
        
        # 4. Create a new DCAOrder record representing the TP (exit) fill
        tp_side = "sell" if dca_entry_order.side.lower() == "buy" else "buy"
        
        tp_fill_order = DCAOrder(
            group_id=dca_entry_order.group_id,
            pyramid_id=dca_entry_order.pyramid_id,
            leg_index=999, # Special index for TP exit
            symbol=dca_entry_order.symbol,
            side=tp_side,
            order_type=OrderType.LIMIT, # Assuming TP is a limit order fill
            price=dca_entry_order.tp_price, # Use the TP price of the entry leg
            quantity=dca_entry_order.filled_quantity,
            status=OrderStatus.FILLED, # Mark as already filled
            exchange_order_id="sim_tp_" + str(uuid.uuid4()), # Simulated exchange ID
            filled_quantity=dca_entry_order.filled_quantity,
            avg_fill_price=dca_entry_order.tp_price,
            filled_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("0"),
            tp_percent=Decimal("0"),
            tp_price=Decimal("0")
        )
        session.add(tp_fill_order)
        await session.commit()
        print(f"Created simulated TP fill order: {tp_fill_order.id} with quantity {tp_fill_order.filled_quantity} at price {tp_fill_order.avg_fill_price}.")

        # Re-fetch user to instantiate PositionManagerService (needed to update position stats)
        result = await session.execute(select(User).where(User.id == position_group.user_id))
        user = result.scalars().first()

        if not user:
            print(f"ERROR: User with ID {position_group.user_id} not found for PositionGroup {position_group_id}.")
            return
        
        # Instantiate PositionManagerService
        position_manager_service = PositionManagerService(
            session_factory=AsyncSessionLocal,
            user=user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=GridCalculatorService(),
            order_service_class=OrderService
        )

        print(f"Triggering update_position_stats for PositionGroup {position_group_id}...")
        await position_manager_service.update_position_stats(position_group_id)
        print(f"Successfully triggered update_position_stats for PositionGroup {position_group_id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate Take-Profit (TP) closure for a DCA order.")
    parser.add_argument("position_group_id", type=str, help="The ID of the position group.")
    parser.add_argument("dca_order_id_to_close", type=str, help="The ID of the DCA order to simulate TP closure for.")
    args = parser.parse_args()
    asyncio.run(simulate_tp_closure(args.position_group_id, args.dca_order_id_to_close))
