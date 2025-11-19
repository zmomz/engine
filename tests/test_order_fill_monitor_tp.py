import pytest
from unittest.mock import AsyncMock, MagicMock
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
    exchange_connector = AsyncMock()
    order_service_cls = MagicMock()
    
    service = OrderFillMonitorService(
        session_factory=session_factory,
        dca_order_repository_class=dca_order_repo_cls,
        exchange_connector=exchange_connector,
        order_service_class=order_service_cls,
        polling_interval_seconds=1
    )
    return service

@pytest.mark.asyncio
async def test_check_orders_places_tp(mock_order_fill_monitor_service):
    # Setup order that will become filled
    order1 = DCAOrder(id=uuid.uuid4(), status=OrderStatus.OPEN.value)
    
    repo_instance = mock_order_fill_monitor_service.dca_order_repository_class.return_value
    repo_instance.get_open_and_partially_filled_orders = AsyncMock(return_value=[order1])

    # Setup OrderService to return filled order
    mock_order_service_instance = mock_order_fill_monitor_service.order_service_class.return_value
    
    async def mock_check_status(order):
        order.status = OrderStatus.FILLED.value
        return order
        
    mock_order_service_instance.check_order_status = AsyncMock(side_effect=mock_check_status)
    mock_order_service_instance.place_tp_order = AsyncMock()

    await mock_order_fill_monitor_service._check_orders()
    
    # Verify place_tp_order was called
    mock_order_service_instance.place_tp_order.assert_called_once()
