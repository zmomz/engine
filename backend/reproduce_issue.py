import asyncio
import sys
import os
from decimal import Decimal
from datetime import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.services.position_manager import PositionManagerService
from app.services.order_management import OrderService
from app.repositories.position_group import PositionGroupRepository
from app.repositories.dca_order import DCAOrderRepository

# Setup in-memory DB
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    print("DCAOrder Columns:", [c.name for c in DCAOrder.__table__.columns])
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # 1. Create User
        user = User(username="testuser", email="test@example.com", hashed_password="dummy", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        session.add(user)
        await session.flush()
        
        # 2. Create PositionGroup
        pg = PositionGroup(
            user_id=user.id,
            exchange="binance",
            symbol="BTC/USDT",
            timeframe=15,
            side="long",
            status=PositionGroupStatus.LIVE,
            total_dca_legs=1,
            base_entry_price=Decimal("50000"),
            weighted_avg_entry=Decimal("50000"),
            tp_mode="per_leg",
            total_filled_quantity=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(pg)
        await session.flush()
        
        # 3. Create Pyramid
        pyramid = Pyramid(
            group_id=pg.id,
            pyramid_index=0,
            entry_price=Decimal("50000"),
            status=PyramidStatus.PENDING,
            dca_config={}
        )
        session.add(pyramid)
        await session.flush()
        
        # 4. Create DCAOrder (Filled)
        order = DCAOrder(
            group_id=pg.id,
            pyramid_id=pyramid.id,
            leg_index=0,
            symbol="BTC/USDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            status=OrderStatus.FILLED.value,
            filled_quantity=Decimal("1.0"),
            avg_fill_price=Decimal("50000"),
            gap_percent=Decimal("0"),
            weight_percent=Decimal("0"),
            tp_percent=Decimal("1.0"),
            tp_price=Decimal("51000"), # 1000 profit
            tp_hit=False,
            tp_order_id="tp_123",
            created_at=datetime.utcnow()
        )
        session.add(order)
        await session.flush()
        await session.commit()
        
        print(f"Initial State: PG Status={pg.status}, PnL={pg.realized_pnl_usd}, NetQty={pg.total_filled_quantity}")

        # 5. Setup Services
        # Mock Exchange Connector
        mock_connector = AsyncMock()
        # Mock get_order_status for TP order to return FILLED
        mock_connector.get_order_status.return_value = {
            "status": "filled",
            "filled": 1.0,
            "average": 51000
        }
        
        order_service = OrderService(session, user, mock_connector)
        
        # We need a fresh PositionManagerService
        # It needs a session_factory, but we are passing session explicitly to update_position_stats
        # So session_factory can be dummy
        mock_session_factory = MagicMock()
        
        # We need grid_calculator_service (can be mocked)
        mock_grid_calc = MagicMock()
        
        pm_service = PositionManagerService(
            session_factory=mock_session_factory,
            user=user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=mock_grid_calc,
            order_service_class=OrderService,
            exchange_connector=mock_connector
        )
        
        # 6. Simulate OrderFillMonitor loop
        # Fetch order from DB
        dca_repo = DCAOrderRepository(session)
        orders = await dca_repo.get_open_and_partially_filled_orders_for_user(user.id)
        # Note: get_open_and_partially_filled_orders_for_user logic:
        # or_(status in [OPEN, PARTIAL], and_(status=FILLED, tp_order_id!=None, tp_hit=False))
        # So it should return our filled order
        
        print(f"Orders found: {len(orders)}")
        if not orders:
            print("Error: No orders found to monitor!")
            return

        target_order = orders[0]
        
        # Check TP status
        updated_order = await order_service.check_tp_status(target_order)
        print(f"Order TP Hit: {updated_order.tp_hit}")
        
        if updated_order.tp_hit:
            print("Updating position stats...")
            # Pass the SAME session
            await pm_service.update_position_stats(updated_order.group_id, session=session)
            
        # Commit as OrderFillMonitor would
        await session.commit()
        
        # 7. Verify Results
        # Reload PG
        pg_repo = PositionGroupRepository(session)
        final_pg = await pg_repo.get(pg.id)
        
        print(f"Final State: PG Status={final_pg.status}, PnL={final_pg.realized_pnl_usd}, NetQty={final_pg.total_filled_quantity}")
        
        if final_pg.realized_pnl_usd == Decimal("1000") and final_pg.status == PositionGroupStatus.CLOSED:
            print("SUCCESS: Bug NOT reproduced (Logic works correctly).")
        else:
            print("FAILURE: Bug reproduced!")
            print(f"Expected PnL: 1000, Got: {final_pg.realized_pnl_usd}")
            print(f"Expected Status: closed, Got: {final_pg.status}")

if __name__ == "__main__":
    asyncio.run(main())
