import asyncio
import os
import sys
import logging
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    async with AsyncSessionLocal() as session:
        # Get users
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        encryption_service = EncryptionService()

        for user in users:
            logger.info(f"Checking user: {user.username}")
            
            # Get open orders
            result = await session.execute(
                select(DCAOrder).where(
                    DCAOrder.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
                )
            )
            orders = result.scalars().all()
            logger.info(f"Found {len(orders)} open orders.")
            
            if not orders:
                continue

            # Setup connector
            try:
                exchange_config = {}
                if isinstance(user.encrypted_api_keys, dict):
                    exchange_key = user.exchange.lower()
                    if exchange_key in user.encrypted_api_keys:
                        exchange_config = user.encrypted_api_keys[exchange_key]
                    else:
                        logger.warning(f"Failed to setup connector for user {user.username}: No API keys found for exchange {user.exchange}.")
                        continue
                elif isinstance(user.encrypted_api_keys, str):
                    # Legacy format: single encrypted string
                    exchange_config = {"encrypted_data": user.encrypted_api_keys}
                else:
                    logger.warning(f"Failed to setup connector for user {user.username}: Invalid API keys format.")
                    continue
                
                if "encrypted_data" not in exchange_config:
                    logger.warning(f"Failed to setup connector for user {user.username}: 'encrypted_data' key not found in exchange configuration for {user.exchange}.")
                    continue

                connector = get_exchange_connector(
                    exchange_type=user.exchange,
                    exchange_config=exchange_config
                )
            except Exception as e:
                logger.error(f"Failed to setup connector for user {user.username}: {e}")
                continue

            order_service = OrderService(session, user, connector)
            
            for order in orders:
                logger.info(f"Cancelling order {order.id} ({order.symbol})...")
                try:
                    await order_service.cancel_order(order)
                    logger.info("Cancelled.")
                except Exception as e:
                    logger.error(f"Failed to cancel: {e}")
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
                    logger.info(f"Closing group {g.id}")
                    g.status = PositionGroupStatus.CLOSED
                    session.add(g)
            
            await session.commit()
            if hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                 await connector.exchange.close()

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(main())
