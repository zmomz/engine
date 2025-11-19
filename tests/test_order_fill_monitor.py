import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import uuid

from app.services.order_fill_monitor import OrderFillMonitorService
from app.models.dca_order import DCAOrder, OrderStatus

@pytest.fixture
def mock_order_fill_monitor_service():
    # Mock dependencies
    session_factory = MagicMock()
    # We need to mock the async generator for session_factory
    async def mock_session_gen():
        yield AsyncMock()
    session_factory.side_effect = mock_session_gen

    dca_order_repo_cls = MagicMock()
    position_group_repo_cls = MagicMock()
    exchange_connector = AsyncMock()
    order_service_cls = MagicMock()
    position_manager_service_cls = MagicMock()
    
    service = OrderFillMonitorService(
        session_factory=session_factory,
        dca_order_repository_class=dca_order_repo_cls,
        position_group_repository_class=position_group_repo_cls,
        exchange_connector=exchange_connector,
        order_service_class=order_service_cls,
        position_manager_service_class=position_manager_service_cls,
        polling_interval_seconds=1
    )
    return service

@pytest.mark.asyncio
async def test_check_orders_no_orders(mock_order_fill_monitor_service):
    # Setup repo to return empty list
    repo_instance = mock_order_fill_monitor_service.dca_order_repository_class.return_value
    repo_instance.get_open_and_partially_filled_orders = AsyncMock(return_value=[])

    await mock_order_fill_monitor_service._check_orders()
    
    # Verify check_order_status was NOT called
    mock_order_service_instance = mock_order_fill_monitor_service.order_service_class.return_value
    mock_order_service_instance.check_order_status.assert_not_called()

@pytest.mark.asyncio
async def test_check_orders_updates_status(mock_order_fill_monitor_service):
    # Setup orders
    group_id = uuid.uuid4()
    order1 = DCAOrder(id=uuid.uuid4(), group_id=group_id, status=OrderStatus.OPEN.value)
    order2 = DCAOrder(id=uuid.uuid4(), status=OrderStatus.PARTIALLY_FILLED.value)
    
    repo_instance = mock_order_fill_monitor_service.dca_order_repository_class.return_value
    repo_instance.get_open_and_partially_filled_orders = AsyncMock(return_value=[order1, order2])

    # Setup OrderService to return updated order
    mock_order_service_instance = mock_order_fill_monitor_service.order_service_class.return_value
    
    async def mock_check_status(order):
        # Simulate status change
        if order.id == order1.id:
             order.status = OrderStatus.FILLED.value
        return order
        
    mock_order_service_instance.check_order_status = AsyncMock(side_effect=mock_check_status)
    mock_order_service_instance.place_tp_order = AsyncMock()

    # Also ensure update_position_stats is an AsyncMock
    mock_position_manager_instance = mock_order_fill_monitor_service.position_manager_service_class.return_value
    mock_position_manager_instance.update_position_stats = AsyncMock()

    await mock_order_fill_monitor_service._check_orders()
    
    # Verify check_order_status was called for both
    assert mock_order_service_instance.check_order_status.await_count == 2
    
    # Verify update_position_stats was called for the filled order
    mock_position_manager_instance = mock_order_fill_monitor_service.position_manager_service_class.return_value
    mock_position_manager_instance.update_position_stats.assert_called_once_with(order1.group_id)
    
    # Verify place_tp_order was called for the filled order
    mock_order_service_instance.place_tp_order.assert_called_once_with(order1)