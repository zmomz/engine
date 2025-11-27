import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid
from datetime import datetime

from app.models.user import User
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.services.order_management import OrderService
from app.services.position_manager import PositionManagerService
from app.services.order_fill_monitor import OrderFillMonitorService
from app.repositories.dca_order import DCAOrderRepository
from app.repositories.position_group import PositionGroupRepository

@pytest.mark.asyncio
async def test_full_lifecycle_tp_fill(db_session):
    # Setup Data
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    
    # Mock User
    user = User(id=user_id, username="test", email="test@test.com", hashed_password="hash", encrypted_api_keys={"binance": {"encrypted_data": "dummy"}})
    db_session.add(user)
    
    # Mock Position Group
    group = PositionGroup(
        id=group_id,
        user_id=user_id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        tp_mode="per_leg"
    )
    db_session.add(group)
    
    # Mock Pyramid
    pyramid_id = uuid.uuid4()
    pyramid = Pyramid(
        id=pyramid_id,
        group_id=group_id,
        pyramid_index=0,
        entry_price=Decimal("50000"),
        entry_timestamp=datetime.utcnow(),
        status=PyramidStatus.FILLED,
        dca_config={}
    )
    db_session.add(pyramid)
    
    # Mock Order (Filled, TP Placed but not hit)
    order = DCAOrder(
        group_id=group_id,
        pyramid_id=pyramid_id,
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        price=Decimal("50000"),
        quantity=Decimal("1.0"),
        status=OrderStatus.FILLED,
        filled_quantity=Decimal("1.0"),
        avg_fill_price=Decimal("50000"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("100"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("50500"),
        tp_order_id="tp_123",
        tp_hit=False
    )
    db_session.add(order)
    await db_session.commit()

    # Mocks
    mock_exchange = AsyncMock()
    # Mock TP status check response
    mock_exchange.get_order_status.return_value = {"status": "filled", "id": "tp_123"}
    
    with patch("app.services.order_fill_monitor.get_exchange_connector", return_value=mock_exchange), \
         patch("app.services.order_fill_monitor.EncryptionService") as MockEnc:
         
        MockEnc.return_value.decrypt_keys.return_value = ("api", "secret")
        
        # Initialize Service
        monitor = OrderFillMonitorService(
            session_factory=lambda: db_session, # simplistic factory for test
            dca_order_repository_class=DCAOrderRepository,
            position_group_repository_class=PositionGroupRepository,
            order_service_class=OrderService,
            position_manager_service_class=PositionManagerService
        )
        
        # Inject our session into the "factory" context
        # Since we passed a lambda returning the session, we need to mock the async context manager behavior
        # But AsyncSession is an async context manager itself.
        # However, calling it again might be tricky if it's already active.
        # Let's bypass the service loop and call `_check_orders` directly, patching session_factory logic inside?
        # Actually, let's just patch the repository retrieval in `_check_orders` or better yet, 
        # let's just test the logic flow by calling the inner components manually to verify they work together.
        
        # 1. Verify Repository fetches the order
        repo = DCAOrderRepository(db_session)
        orders = await repo.get_open_and_partially_filled_orders_for_user(user_id)
        assert len(orders) == 1
        assert orders[0].id == order.id
        
        # 2. Run logic manually (simulating the loop body)
        order_service = OrderService(db_session, user, mock_exchange)
        pos_manager = PositionManagerService(lambda: db_session, user, PositionGroupRepository, None, OrderService, mock_exchange)
        
        # Simulate Loop Step: Check TP
        updated_order = await order_service.check_tp_status(orders[0])
        assert updated_order.tp_hit == True
        
        # Simulate Loop Step: Update Stats
        await pos_manager.update_position_stats(group_id, session=db_session)
        
        await db_session.refresh(group)
        
        # Verify Results
        assert group.realized_pnl_usd == Decimal("500.0") # (50500 - 50000) * 1.0
        assert group.total_filled_quantity == Decimal("0.0") # Net quantity 0
        assert group.status == PositionGroupStatus.CLOSED
        assert group.closed_at is not None
