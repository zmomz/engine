import asyncio
import os
import sys
from sqlalchemy import select

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.services.order_management import OrderService
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService

async def main():
    async with AsyncSessionLocal() as session:
        # Get users
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        encryption_service = EncryptionService()

        for user in users:
            print(f"Checking user: {user.username}")
            
            # Get open orders
            result = await session.execute(
                select(DCAOrder).where(
                    DCAOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
                )
            )
            orders = result.scalars().all()
            print(f"Found {len(orders)} open orders.")
            
            if not orders:
                continue

            # Setup connector
            try:
                encrypted_data = user.encrypted_api_keys
                if isinstance(encrypted_data, dict) and user.exchange in encrypted_data:
                     encrypted_data = encrypted_data.get(user.exchange)
                
                api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
                connector = get_exchange_connector(
                    exchange_type=user.exchange,
                    api_key=api_key,
                    secret_key=secret_key
                )
            except Exception as e:
                print(f"Failed to setup connector: {e}")
                continue

            order_service = OrderService(session, user, connector)
            
            for order in orders:
                print(f"Cancelling order {order.id} ({order.symbol})...")
                try:
                    await order_service.cancel_order(order)
                    print("Cancelled.")
                except Exception as e:
                    print(f"Failed to cancel: {e}")
                    # Force mark as cancelled in DB if exchange fails (e.g. order not found)
                    order.status = OrderStatus.CANCELLED
                    order.cancelled_at = datetime.utcnow()
                    session.add(order)
            
            await session.commit()
            
            # Now close the groups
            result = await session.execute(
                select(PositionGroup).where(
                    PositionGroup.user_id == user.id,
                    PositionGroup.status.in_([PositionGroupStatus.LIVE, PositionGroupStatus.ACTIVE, PositionGroupStatus.PARTIALLY_FILLED])
                )
            )
            groups = result.scalars().all()
            for g in groups:
                # Check if all orders are closed
                await session.refresh(g, attribute_names=["dca_orders"])
                all_closed = all(o.status in [OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.FAILED] for o in g.dca_orders)
                if all_closed:
                    print(f"Closing group {g.id}")
                    g.status = PositionGroupStatus.CLOSED
                    session.add(g)
            
            await session.commit()
            if hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                 await connector.exchange.close()

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
