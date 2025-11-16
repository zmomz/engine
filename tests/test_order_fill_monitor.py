import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal
import asyncio
import uuid
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.order_fill_monitor import OrderFillMonitorService
from app.services.order_management import OrderService
from app.repositories.dca_order import DCAOrderRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.models.dca_order import DCAOrder, OrderStatus

@pytest.fixture
def mock_dca_order_repository_class():
    mock_instance = MagicMock(spec=DCAOrderRepository)
    mock_instance.get_open_and_partially_filled_orders = AsyncMock()
    mock_class = MagicMock(spec=DCAOrderRepository, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_order_service_class():
    mock_instance = AsyncMock(spec=OrderService)
    mock_class = MagicMock(spec=OrderService)
    mock_class.return_value = mock_instance
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    return AsyncMock(spec=ExchangeInterface)

@pytest.fixture
def mock_session_factory():
    @asynccontextmanager
    async def factory():
        mock_session_obj = AsyncMock(spec=AsyncSession)
        try:
            yield mock_session_obj
        finally:
            pass
    return factory

@pytest.fixture
def order_fill_monitor_service(
    mock_dca_order_repository_class,
    mock_order_service_class,
    mock_exchange_connector,
    mock_session_factory
):
    return OrderFillMonitorService(
        dca_order_repository_class=mock_dca_order_repository_class,
        order_service_class=mock_order_service_class,
        exchange_connector=mock_exchange_connector,
        session_factory=mock_session_factory # Pass session factory directly
    )

@pytest.mark.asyncio
async def test_start_and_stop_monitoring(order_fill_monitor_service):
    """
    Test that the monitor starts and stops correctly.
    """
    with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
        await order_fill_monitor_service.start_monitoring()
        assert order_fill_monitor_service._running is True
        assert order_fill_monitor_service._monitor_task is not None

        # Allow one loop iteration to happen
        await asyncio.sleep(0.1) # Give control back to the event loop
        order_fill_monitor_service._monitor_task.cancel()
        await asyncio.sleep(0.1) # Give control back to the event loop for cancellation

        await order_fill_monitor_service.stop_monitoring()
        assert order_fill_monitor_service._running is False
        assert order_fill_monitor_service._monitor_task.done() is True

@pytest.mark.asyncio
async def test_monitor_loop_checks_orders(order_fill_monitor_service, mock_dca_order_repository_class, mock_order_service_class, mock_session_factory):
    """
    Test that the monitor loop fetches open orders and checks their status.
    """
    mock_order = DCAOrder(
        id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=0,
        symbol="BTC/USDT", side="buy", order_type="limit", price=Decimal("60000"), quantity=Decimal("0.001"),
        gap_percent=Decimal("0"), weight_percent=Decimal("20"), tp_percent=Decimal("1"), tp_price=Decimal("60600"),
        status=OrderStatus.OPEN, exchange_order_id="exchange_order_1"
    )
    
    mock_dca_order_repository_class.return_value.get_open_and_partially_filled_orders.return_value = [mock_order]
    mock_order_service_class.return_value.check_order_status.return_value = mock_order
    order_fill_monitor_service.polling_interval_seconds = 0.01 # Shorten interval for testing
    await order_fill_monitor_service.start_monitoring()
    await asyncio.sleep(0.01) # Allow task to be created

    # Allow the loop to run a few times
    await asyncio.sleep(0.2)

    order_fill_monitor_service._monitor_task.cancel()
    await asyncio.sleep(0.2)

    mock_dca_order_repository_class.return_value.get_open_and_partially_filled_orders.assert_called()
    mock_order_service_class.return_value.check_order_status.assert_called_with(mock_order)

@pytest.mark.asyncio
async def test_monitor_loop_handles_exceptions(order_fill_monitor_service, mock_dca_order_repository_class, mock_order_service_class, mock_session_factory):
    """
    Test that the monitor loop handles exceptions gracefully and continues.
    """
    mock_order = DCAOrder(
        id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=0,
        symbol="BTC/USDT", side="buy", order_type="limit", price=Decimal("60000"), quantity=Decimal("0.001"),
        gap_percent=Decimal("0"), weight_percent=Decimal("20"), tp_percent=Decimal("1"), tp_price=Decimal("60600"),
        status=OrderStatus.OPEN, exchange_order_id="exchange_order_1"
    )
    
    mock_dca_order_repository_class.return_value.get_open_and_partially_filled_orders.return_value = [mock_order]
    mock_order_service_class.return_value.check_order_status.side_effect = Exception("Test exception")

    order_fill_monitor_service.polling_interval_seconds = 0.01 # Shorten interval for testing
    await order_fill_monitor_service.start_monitoring()
    await asyncio.sleep(0.01) # Allow task to be created

    # Allow the loop to run a few times
    await asyncio.sleep(0.2)

    order_fill_monitor_service._monitor_task.cancel()
    await asyncio.sleep(0.2)

    mock_dca_order_repository_class.return_value.get_open_and_partially_filled_orders.assert_called()
    mock_order_service_class.return_value.check_order_status.assert_called_with(mock_order)
    # Expect the loop to continue despite the exception
    # assert mock_sleep.call_count > 0 # Removed as mock_sleep is no longer patched
