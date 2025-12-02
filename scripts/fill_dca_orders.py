import asyncio
import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.user import User
from app.models.position_group import PositionGroup # Added import for PositionGroup
from app.services.position_manager import PositionManagerService
from app.repositories.position_group import PositionGroupRepository
from app.services.grid_calculator import GridCalculatorService # Needed for PositionManagerService init
from app.services.order_management import OrderService # Needed for PositionManagerService init
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig # Needed for PositionManagerService init

async def fill_open_dca_orders():
    async with AsyncSessionLocal() as session:
        print("Fetching open DCA orders...")
        result = await session.execute(select(DCAOrder).where(DCAOrder.status == OrderStatus.OPEN))
        open_orders = result.scalars().all()

        if not open_orders:
            print("No open DCA orders found to fill.")
            return

        print(f"Found {len(open_orders)} open DCA orders. Filling them...")
        
        position_group_id_to_update = None
        for order in open_orders:
            order.status = OrderStatus.FILLED
            # Set filled_quantity to quantity if not already set
            if order.filled_quantity is None or order.filled_quantity == Decimal("0"):
                order.filled_quantity = order.quantity
            # Set avg_fill_price to price if not already set
            if order.avg_fill_price is None or order.avg_fill_price == Decimal("0"):
                order.avg_fill_price = order.price
            order.filled_at = datetime.utcnow()
            session.add(order)
            print(f"  - Filled Order ID: {order.id}, Symbol: {order.symbol}, Quantity: {order.filled_quantity}")
            if not position_group_id_to_update:
                position_group_id_to_update = order.group_id

        await session.commit()
        print("All open DCA orders have been marked as FILLED.")

        if position_group_id_to_update:
            # Re-fetch the user to instantiate PositionManagerService
            result = await session.execute(select(PositionGroup).where(PositionGroup.id == position_group_id_to_update))
            position_group_obj = result.scalars().first()
            if not position_group_obj:
                print(f"ERROR: PositionGroup {position_group_id_to_update} not found after filling orders.")
                return
            
            user_id = position_group_obj.user_id
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()

            if not user:
                print(f"ERROR: User with ID {user_id} not found for PositionGroup {position_group_id_to_update}.")
                return
            
            # Retrieve risk config directly from user object
            risk_config = RiskEngineConfig(**user.risk_config)
            dca_grid_config = DCAGridConfig(**user.dca_grid_config) # Retrieve dca grid config

            position_manager_service = PositionManagerService(
                session_factory=AsyncSessionLocal,
                user=user,
                position_group_repository_class=PositionGroupRepository,
                grid_calculator_service=GridCalculatorService(),
                order_service_class=OrderService
            )

            # Place TP orders for newly filled orders if tp_mode is per_leg
            if dca_grid_config.tp_mode == "per_leg":
                order_service = position_manager_service.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=position_manager_service._get_exchange_connector_for_user(user, position_group_obj.exchange) # Get connector
                )
                for order in open_orders: # open_orders now contain the filled orders
                    if order.status == OrderStatus.FILLED and not order.tp_order_id:
                        print(f"Placing TP order for DCA order {order.id} (Leg Index: {order.leg_index})...")
                        await order_service.place_tp_order(order)


            print(f"Triggering update_position_stats for PositionGroup {position_group_id_to_update}...")
            updated_position_group = await position_manager_service.update_position_stats(position_group_id_to_update, session=session)
            print(f"Triggering update_risk_timer for PositionGroup {position_group_id_to_update}...")
            if updated_position_group:
                await position_manager_service.update_risk_timer(position_group_id_to_update, risk_config, session=session, position_group=updated_position_group)
            else:
                print(f"ERROR: Could not retrieve updated position group for {position_group_id_to_update}")
            await session.commit() # Commit changes made by update_position_stats and update_risk_timer
            print(f"Successfully triggered update_position_stats and update_risk_timer for PositionGroup {position_group_id_to_update}.")

if __name__ == "__main__":
    asyncio.run(fill_open_dca_orders())