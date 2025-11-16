import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal
import uuid
import asyncio

from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.repositories.dca_order import DCAOrderRepository
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.exceptions import APIError, ExchangeConnectionError

@pytest.fixture
def mock_exchange_connector():
    return AsyncMock(spec=ExchangeInterface)

@pytest.fixture
def mock_dca_order_repository():
    return AsyncMock(spec=DCAOrderRepository)

@pytest.fixture
def order_service(mock_exchange_connector, mock_dca_order_repository):
    return OrderService(mock_exchange_connector, mock_dca_order_repository)

@pytest.mark.asyncio
async def test_submit_order_success(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test successful order submission and initial DB update.
    """
    mock_dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("60000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("60600"),
        status=OrderStatus.PENDING,
    )

    mock_exchange_connector.place_order.return_value = {
        "id": "exchange_order_123",
        "status": "open",
        "datetime": datetime.utcnow().isoformat(),
        "timestamp": datetime.utcnow().timestamp() * 1000,
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "buy",
        "price": 60000,
        "amount": 0.001,
        "filled": 0,
        "remaining": 0.001,
        "cost": 0,
        "fee": 0,
        "info": {}
    }

    updated_order = await order_service.submit_order(mock_dca_order)

    mock_exchange_connector.place_order.assert_awaited_once_with(
        symbol="BTC/USDT",
        type="limit",
        side="buy",
        amount=Decimal("0.001"),
        price=Decimal("60000")
    )
    mock_dca_order_repository.update.assert_awaited_once()
    assert updated_order.exchange_order_id == "exchange_order_123"
    assert updated_order.status == OrderStatus.OPEN
    assert updated_order.submitted_at is not None

@pytest.mark.asyncio
async def test_cancel_order_success(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test successful order cancellation and DB update.
    """
    mock_dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("60000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("60600"),
        status=OrderStatus.OPEN,
        exchange_order_id="exchange_order_123"
    )

    mock_exchange_connector.cancel_order.return_value = {
        "id": "exchange_order_123",
        "status": "canceled",
        "datetime": datetime.utcnow().isoformat(),
        "timestamp": datetime.utcnow().timestamp() * 1000,
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "buy",
        "price": 60000,
        "amount": 0.001,
        "filled": 0,
        "remaining": 0,
        "cost": 0,
        "fee": 0,
        "info": {}
    }

    updated_order = await order_service.cancel_order(mock_dca_order)

    mock_exchange_connector.cancel_order.assert_awaited_once_with(
        order_id="exchange_order_123",
        symbol="BTC/USDT"
    )
    mock_dca_order_repository.update.assert_awaited_once()
    assert updated_order.status == OrderStatus.CANCELLED
    assert updated_order.cancelled_at is not None

@pytest.mark.asyncio
async def test_check_order_status_filled(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test checking order status when the order is filled.
    """
    mock_dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("60000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("60600"),
        status=OrderStatus.OPEN,
        exchange_order_id="exchange_order_123"
    )

    mock_exchange_connector.get_order_status.return_value = {
        "id": "exchange_order_123",
        "status": "filled",
        "datetime": datetime.utcnow().isoformat(),
        "timestamp": datetime.utcnow().timestamp() * 1000,
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "buy",
        "price": 60000,
        "amount": 0.001,
        "filled": 0.001,
        "remaining": 0,
        "cost": 60,
        "fee": 0.06,
        "fee_currency": "USDT",
        "info": {}
    }

    updated_order = await order_service.check_order_status(mock_dca_order)

    mock_exchange_connector.get_order_status.assert_awaited_once_with(
        order_id="exchange_order_123",
        symbol="BTC/USDT"
    )
    mock_dca_order_repository.update.assert_awaited_once()
    assert updated_order.status == OrderStatus.FILLED
    assert updated_order.filled_quantity == Decimal("0.001")
    assert updated_order.avg_fill_price == Decimal("60000")
    assert updated_order.filled_at is not None

@pytest.mark.asyncio
async def test_submit_order_with_retries(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test that submit_order retries on ExchangeConnectionError with exponential backoff.
    """
    mock_dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("60000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("60600"),
        status=OrderStatus.PENDING,
    )

    # Configure mock to raise ExchangeConnectionError twice, then succeed
    mock_exchange_connector.place_order.side_effect = [
        ExchangeConnectionError("Connection lost"),
        ExchangeConnectionError("Connection timed out"),
        {
            "id": "exchange_order_123",
            "status": "open",
            "datetime": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().timestamp() * 1000,
            "symbol": "BTC/USDT",
            "type": "limit",
            "side": "buy",
            "price": 60000,
            "amount": 0.001,
            "filled": 0,
            "remaining": 0.001,
            "cost": 0,
            "fee": 0,
            "info": {}
        }
    ]

    # Patch asyncio.sleep to prevent actual delays during testing
    with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
        updated_order = await order_service.submit_order(mock_dca_order)

        assert mock_exchange_connector.place_order.call_count == 3
        mock_sleep.assert_any_await(1)  # First retry delay
        mock_sleep.assert_any_await(2)  # Second retry delay
        mock_dca_order_repository.update.assert_awaited_once()
        assert updated_order.status == OrderStatus.OPEN

@pytest.mark.asyncio
async def test_startup_reconciliation(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test that startup reconciliation correctly updates order statuses.
    """
    # Orders in DB (some open, some filled but marked open in DB, some cancelled but marked open in DB)
    db_order_1 = DCAOrder(
        id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=0,
        symbol="BTC/USDT", side="buy", order_type="limit", price=Decimal("60000"), quantity=Decimal("0.001"),
        gap_percent=Decimal("0"), weight_percent=Decimal("20"), tp_percent=Decimal("1"), tp_price=Decimal("60600"),
        status=OrderStatus.OPEN, exchange_order_id="exchange_order_1"
    )
    db_order_2 = DCAOrder(
        id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=1,
        symbol="ETH/USDT", side="buy", order_type="limit", price=Decimal("3000"), quantity=Decimal("0.01"),
        gap_percent=Decimal("0"), weight_percent=Decimal("20"), tp_percent=Decimal("1"), tp_price=Decimal("3030"),
        status=OrderStatus.OPEN, exchange_order_id="exchange_order_2" # Should be filled on exchange
    )
    db_order_3 = DCAOrder(
        id=uuid.uuid4(), group_id=uuid.uuid4(), pyramid_id=uuid.uuid4(), leg_index=2,
        symbol="XRP/USDT", side="buy", order_type="limit", price=Decimal("0.5"), quantity=Decimal("100"),
        gap_percent=Decimal("0"), weight_percent=Decimal("20"), tp_percent=Decimal("1"), tp_price=Decimal("0.505"),
        status=OrderStatus.OPEN, exchange_order_id="exchange_order_3" # Should be cancelled on exchange
    )

    mock_dca_order_repository.get_all_open_orders.return_value = [db_order_1, db_order_2, db_order_3]

    # Exchange state
    mock_exchange_connector.get_order_status.side_effect = [
        # Status for db_order_1 (still open)
        {
            "id": "exchange_order_1", "status": "open", "datetime": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().timestamp() * 1000, "symbol": "BTC/USDT", "type": "limit",
            "side": "buy", "price": 60000, "amount": 0.001, "filled": 0, "remaining": 0.001,
            "cost": 0, "fee": 0, "info": {}
        },
        # Status for db_order_2 (filled on exchange)
        {
            "id": "exchange_order_2", "status": "filled", "datetime": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().timestamp() * 1000, "symbol": "ETH/USDT", "type": "limit",
            "side": "buy", "price": 3000, "amount": 0.01, "filled": 0.01, "remaining": 0,
            "cost": 30, "fee": 0.03, "fee_currency": "USDT", "info": {}
        },
        # Status for db_order_3 (cancelled on exchange)
        {
            "id": "exchange_order_3", "status": "canceled", "datetime": datetime.utcnow().isoformat(),
            "timestamp": datetime.utcnow().timestamp() * 1000, "symbol": "XRP/USDT", "type": "limit",
            "side": "buy", "price": 0.5, "amount": 100, "filled": 0, "remaining": 0,
            "cost": 0, "fee": 0, "info": {}
        }
    ]

    await order_service.reconcile_open_orders()

    # Assertions
    mock_dca_order_repository.get_all_open_orders.assert_awaited_once()
    assert mock_exchange_connector.get_order_status.call_count == 3
    assert mock_dca_order_repository.update.call_count == 2 # db_order_2 and db_order_3 should be updated

    assert db_order_1.status == OrderStatus.OPEN
    assert db_order_2.status == OrderStatus.FILLED
    assert db_order_2.filled_quantity == Decimal("0.01")
    assert db_order_2.avg_fill_price == Decimal("3000")
    assert db_order_3.status == OrderStatus.CANCELLED
