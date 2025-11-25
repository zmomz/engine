import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from app.services.order_fill_monitor import OrderFillMonitorService
from app.models.dca_order import DCAOrder, OrderStatus
from app.repositories.position_group import PositionGroupRepository # Added
from decimal import Decimal
from app.services.order_management import OrderService
from app.services.position_manager import PositionManagerService # Added

@pytest.fixture
def mock_order_fill_monitor_service():
    # Mock dependencies
    @asynccontextmanager
    async def mock_session_gen():
        mock_session_obj = AsyncMock()
        mock_session_obj.commit = AsyncMock()
        mock_session_obj.rollback = AsyncMock()
        yield mock_session_obj
    session_factory = mock_session_gen

    dca_order_repo_cls = MagicMock()
    position_group_repo_cls = MagicMock(spec=PositionGroupRepository) # Added
    order_service_cls = MagicMock()
    position_manager_service_cls = MagicMock(spec=PositionManagerService) # Added
    
    service = OrderFillMonitorService(
        session_factory=session_factory,
        dca_order_repository_class=dca_order_repo_cls,
        position_group_repository_class=position_group_repo_cls, # Added
        order_service_class=order_service_cls,
        position_manager_service_class=position_manager_service_cls, # Added
        polling_interval_seconds=1
    )
    return service

@pytest.mark.asyncio
async def test_check_orders_places_tp(mock_order_fill_monitor_service):
        # Setup order that will become filled
        order1 = DCAOrder(
            id=uuid.uuid4(), 
            group_id=uuid.uuid4(),
            pyramid_id=uuid.uuid4(),
            symbol="BTC/USDT", 
            status=OrderStatus.OPEN.value,
            exchange_order_id="exchange_order_123",
            tp_price=Decimal("60000"),
            side="buy", # Added side for place_tp_order
            filled_quantity=Decimal("0.001") # Added filled_quantity
        )
        
        mock_group = MagicMock()
        mock_group.exchange = "binance"
        order1.group = mock_group
    
        # Mock the DCAOrderRepository to return our test order
        # Make sure get_open_and_partially_filled_orders is an AsyncMock so it can be awaited
        mock_repo_instance = mock_order_fill_monitor_service.dca_order_repository_class.return_value
        mock_repo_instance.get_open_and_partially_filled_orders = AsyncMock(return_value=[order1])
    
        # Create a mock instance of OrderService that will be returned when OrderService is instantiated
        mock_order_service_instance = AsyncMock(spec=OrderService)
        
        # Configure the mock OrderService *class* to return our pre-configured instance
        mock_order_fill_monitor_service.order_service_class.return_value = mock_order_service_instance
    
        # Configure the check_order_status to return a filled order
        async def mock_check_order_status_side_effect(order_to_check):
            order_to_check.status = OrderStatus.FILLED.value
            order_to_check.filled_at = datetime.utcnow()
            return order_to_check
        mock_order_service_instance.check_order_status.side_effect = mock_check_order_status_side_effect
    
        # Mock place_tp_order
        mock_order_service_instance.place_tp_order = AsyncMock(return_value=order1)
    
        # Mock PositionManagerService's update_position_stats method
        mock_order_fill_monitor_service.position_manager_service_class.return_value.update_position_stats = AsyncMock()
    
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.encrypted_api_keys = {"encrypted_data": "mock"}
        mock_user.exchange = "binance"

        with patch("app.services.order_fill_monitor.UserRepository") as mock_user_repo_cls, \
             patch("app.services.order_fill_monitor.get_exchange_connector"):
            mock_user_repo_instance = mock_user_repo_cls.return_value
            mock_user_repo_instance.get_all_active_users = AsyncMock(return_value=[mock_user])

            await mock_order_fill_monitor_service._check_orders()
    
        # Verify place_tp_order was called
        mock_order_service_instance.place_tp_order.assert_awaited_once_with(order1)
        mock_order_fill_monitor_service.position_manager_service_class.return_value.update_position_stats.assert_awaited_once_with(order1.group_id, session=ANY)