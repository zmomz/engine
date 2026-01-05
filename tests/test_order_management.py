import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal
import uuid
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.repositories.dca_order import DCAOrderRepository
from app.models.dca_order import DCAOrder, OrderStatus, OrderType
from app.models.user import User 
from app.exceptions import APIError, ExchangeConnectionError

@pytest.fixture
async def user_id_fixture(db_session: AsyncMock):
    user = User(
        id=uuid.uuid4(),
        username="testuser_om",
        email="test_om@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id

@pytest.fixture
def mock_exchange_connector():
    return AsyncMock(spec=ExchangeInterface)

@pytest.fixture
def mock_dca_order_repository(db_session: AsyncMock):
    return AsyncMock(spec=DCAOrderRepository, return_value=DCAOrderRepository(db_session))

@pytest.fixture
async def order_service(db_session: AsyncMock, user_id_fixture, mock_exchange_connector, mock_dca_order_repository):
    # Fetch a dummy user object to pass to OrderService
    user = await db_session.get(User, user_id_fixture)
    if user is None:
        # Create a dummy user if not found (should be created by user_id_fixture)
        user = User(
            id=user_id_fixture,
            username="testuser_om_service",
            email="test_om_service@example.com",
            hashed_password="hashedpassword",
            webhook_secret="mock_secret"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

    # Create OrderService and directly inject the mock repository
    service = OrderService(
        session=db_session,
        user=user,
        exchange_connector=mock_exchange_connector
    )
    # Directly assign the mock repository to ensure it's used
    service.dca_order_repository = mock_dca_order_repository
    yield service

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
        order_type=OrderType.LIMIT.value.upper(),
        side=mock_dca_order.side.upper(),
        quantity=Decimal("0.001"),
        price=Decimal("60000"),
        amount_type="base"
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
        "average": 60000,
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
    # Verify fee extraction from exchange response
    assert updated_order.fee == Decimal("0.06")
    assert updated_order.fee_currency == "USDT"

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

    # Patch both asyncio.sleep and random.uniform to make delays predictable
    # random.uniform adds jitter to the delay, so we mock it to return 0
    with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep, \
         patch('app.services.order_management.random.uniform', return_value=0):
        updated_order = await order_service.submit_order(mock_dca_order)

        assert mock_exchange_connector.place_order.call_count == 3
        # With jitter=0, delays are exactly base_delay * (2 ** attempt): 1, 2
        assert mock_sleep.await_count == 2  # Two retries = two sleeps
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
            "side": "buy", "price": 3000, "average": 3000, "amount": 0.01, "filled": 0.01, "remaining": 0,
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

# --- New Tests ---

@pytest.mark.asyncio
async def test_submit_order_max_retries_exceeded(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test that submit_order fails after max retries and updates order status to FAILED.
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

    # Always raise ExchangeConnectionError
    mock_exchange_connector.place_order.side_effect = ExchangeConnectionError("Connection refused")

    with patch('asyncio.sleep', new=AsyncMock()) as mock_sleep:
        with pytest.raises(APIError) as exc_info:
            await order_service.submit_order(mock_dca_order)
        
        assert "Failed to submit order after 3 attempts" in str(exc_info.value)
        assert mock_exchange_connector.place_order.call_count == 3
        mock_dca_order_repository.update.assert_awaited_once()
        assert mock_dca_order.status == OrderStatus.FAILED.value

@pytest.mark.asyncio
async def test_check_order_status_api_error(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test checking order status when API error occurs (should re-raise APIError, NOT mark as failed).
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

    mock_exchange_connector.get_order_status.side_effect = APIError("Exchange error")

    with pytest.raises(APIError) as exc_info:
        await order_service.check_order_status(mock_dca_order)
    
    assert f"Order not found on exchange for order {mock_dca_order.id}" in str(exc_info.value)
    mock_dca_order_repository.update.assert_not_awaited() # Should not update status
    assert mock_dca_order.status == OrderStatus.OPEN

@pytest.mark.asyncio
async def test_check_order_status_unknown_error(order_service, mock_exchange_connector, mock_dca_order_repository):
    """
    Test checking order status when unknown error occurs (should raise APIError).
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

    mock_exchange_connector.get_order_status.side_effect = Exception("Something went wrong")

    with pytest.raises(APIError) as exc_info:
        await order_service.check_order_status(mock_dca_order)
    
    assert "Failed to retrieve order status: Something went wrong" in str(exc_info.value)
    mock_dca_order_repository.update.assert_not_awaited()
    assert mock_dca_order.status == OrderStatus.OPEN


@pytest.mark.asyncio
async def test_place_tp_order_success(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test successful TP order placement for a filled order."""
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
        status=OrderStatus.FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0.001"),
        avg_fill_price=Decimal("60000"),
        tp_order_id=None
    )

    mock_exchange_connector.place_order.return_value = {
        "id": "tp_order_123",
        "status": "open"
    }
    mock_exchange_connector.get_precision_rules.return_value = {
        "BTC/USDT": {"tick_size": "0.01", "step_size": "0.00001"}
    }

    updated_order = await order_service.place_tp_order(mock_dca_order)

    assert updated_order.tp_order_id == "tp_order_123"
    mock_exchange_connector.place_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_place_tp_order_already_has_tp(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test that TP order is not placed if one already exists."""
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
        status=OrderStatus.FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0.001"),
        tp_order_id="existing_tp_order"  # Already has TP
    )

    result = await order_service.place_tp_order(mock_dca_order)

    assert result.tp_order_id == "existing_tp_order"
    mock_exchange_connector.place_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_place_tp_order_not_filled(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test that TP order cannot be placed for unfilled order."""
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

    with pytest.raises(APIError, match="Cannot place TP order for unfilled order"):
        await order_service.place_tp_order(mock_dca_order)


@pytest.mark.asyncio
async def test_place_tp_order_for_partial_fill(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test TP order placement for partially filled order."""
    mock_dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("60000"),
        quantity=Decimal("0.01"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("60600"),
        status=OrderStatus.PARTIALLY_FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0.005"),
        avg_fill_price=Decimal("60000"),
        tp_order_id=None
    )

    mock_exchange_connector.place_order.return_value = {
        "id": "partial_tp_order",
        "status": "open"
    }
    mock_exchange_connector.get_precision_rules.return_value = {
        "BTC/USDT": {"tick_size": "0.01"}
    }

    result = await order_service.place_tp_order_for_partial_fill(mock_dca_order)

    assert result.tp_order_id == "partial_tp_order"


@pytest.mark.asyncio
async def test_place_tp_order_for_partial_fill_no_filled_quantity(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test that partial TP is not placed when no filled quantity."""
    mock_dca_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=uuid.uuid4(),
        pyramid_id=uuid.uuid4(),
        leg_index=0,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("60000"),
        quantity=Decimal("0.01"),
        gap_percent=Decimal("0"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("60600"),
        status=OrderStatus.PARTIALLY_FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0"),  # No filled quantity
        tp_order_id=None
    )

    result = await order_service.place_tp_order_for_partial_fill(mock_dca_order)

    # Should return same order without placing TP
    mock_exchange_connector.place_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_tp_status_hit(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test checking TP status when TP is hit."""
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
        status=OrderStatus.FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0.001"),
        tp_order_id="tp_order_123",
        tp_hit=False
    )

    mock_exchange_connector.get_order_status.return_value = {
        "id": "tp_order_123",
        "status": "closed",
        "filled": 0.001,
        "average": 60600
    }

    result = await order_service.check_tp_status(mock_dca_order)

    assert result.tp_hit is True


@pytest.mark.asyncio
async def test_check_tp_status_no_tp_order(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test checking TP status when no TP order exists."""
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
        status=OrderStatus.FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0.001"),
        tp_order_id=None  # No TP order
    )

    result = await order_service.check_tp_status(mock_dca_order)

    mock_exchange_connector.get_order_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_order_no_exchange_id(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test cancelling order without exchange_order_id."""
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
        exchange_order_id=None  # No exchange order ID
    )

    result = await order_service.cancel_order(mock_dca_order)

    assert result.status == OrderStatus.CANCELLED
    mock_exchange_connector.cancel_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_tp_order_success(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test successful TP order cancellation."""
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
        status=OrderStatus.FILLED,
        exchange_order_id="exchange_order_123",
        filled_quantity=Decimal("0.001"),
        tp_order_id="tp_order_123",
        tp_hit=False
    )

    mock_exchange_connector.cancel_order.return_value = {
        "id": "tp_order_123",
        "status": "canceled"
    }

    result = await order_service.cancel_tp_order(mock_dca_order)

    assert result.tp_order_id is None
    mock_exchange_connector.cancel_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_tp_order_no_tp(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test TP cancellation when no TP order exists."""
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
        status=OrderStatus.FILLED,
        exchange_order_id="exchange_order_123",
        tp_order_id=None  # No TP order
    )

    result = await order_service.cancel_tp_order(mock_dca_order)

    mock_exchange_connector.cancel_order.assert_not_awaited()


@pytest.mark.asyncio
async def test_place_market_order_success(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test successful market order placement."""
    mock_exchange_connector.place_order.return_value = {
        "id": "market_order_123",
        "status": "closed",
        "filled": 0.001,
        "average": 60000
    }

    result = await order_service.place_market_order(
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTC/USDT",
        side="sell",
        quantity=Decimal("0.001")
    )

    # Verify the order was placed
    assert result["id"] == "market_order_123"
    mock_exchange_connector.place_order.assert_awaited_once()

    # Verify order parameters were correct
    call_args = mock_exchange_connector.place_order.call_args
    assert call_args.kwargs.get("symbol") == "BTC/USDT"
    assert call_args.kwargs.get("side", "").upper() == "SELL"
    assert call_args.kwargs.get("order_type", "").upper() == "MARKET"
    # Check for either 'amount' or 'quantity' parameter
    qty = call_args.kwargs.get("amount") or call_args.kwargs.get("quantity")
    assert qty == Decimal("0.001")

    # Verify result contains expected fields
    assert result["status"] == "closed"
    assert result["filled"] == 0.001


@pytest.mark.asyncio
async def test_place_market_order_with_slippage_warning(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test market order with slippage warning."""
    mock_exchange_connector.place_order.return_value = {
        "id": "market_order_123",
        "status": "closed",
        "filled": 0.001,
        "average": 59400  # 1% slippage for sell
    }

    result = await order_service.place_market_order(
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTC/USDT",
        side="sell",
        quantity=Decimal("0.001"),
        expected_price=Decimal("60000"),
        max_slippage_percent=0.5,  # 0.5% max
        slippage_action="warn"  # Just warn
    )

    # Should complete even with slippage warning
    assert result["id"] == "market_order_123"


@pytest.mark.asyncio
async def test_place_market_order_with_slippage_reject(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test market order rejection when slippage exceeds threshold."""
    from app.exceptions import SlippageExceededError

    mock_exchange_connector.place_order.return_value = {
        "id": "market_order_123",
        "status": "closed",
        "filled": 0.001,
        "average": 59400  # ~1% slippage
    }

    with pytest.raises(SlippageExceededError):
        await order_service.place_market_order(
            user_id=uuid.uuid4(),
            exchange="binance",
            symbol="BTC/USDT",
            side="sell",
            quantity=Decimal("0.001"),
            expected_price=Decimal("60000"),
            max_slippage_percent=0.5,
            slippage_action="reject"
        )


@pytest.mark.asyncio
async def test_place_market_order_with_db_record(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test market order with database recording."""
    position_group_id = uuid.uuid4()

    mock_exchange_connector.place_order.return_value = {
        "id": "market_order_123",
        "status": "closed",
        "filled": 0.001,
        "average": 60000
    }

    result = await order_service.place_market_order(
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTC/USDT",
        side="sell",
        quantity=Decimal("0.001"),
        position_group_id=position_group_id,
        record_in_db=True
    )

    assert result["id"] == "market_order_123"
    mock_dca_order_repository.create.assert_awaited_once()

    # CRITICAL: Verify the created order has correct state
    created_order = mock_dca_order_repository.create.call_args[0][0]
    assert created_order.symbol == "BTC/USDT"
    assert created_order.side == "sell"
    assert created_order.order_type == "market"
    assert created_order.group_id == position_group_id
    assert created_order.exchange_order_id == "market_order_123"
    # Market orders should be immediately filled
    assert created_order.status == OrderStatus.FILLED.value
    assert created_order.filled_quantity == Decimal("0.001")


@pytest.mark.asyncio
async def test_cancel_open_orders_for_group(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test cancelling all open orders for a group."""
    group_id = uuid.uuid4()

    open_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=group_id,
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
        status=OrderStatus.OPEN.value,
        exchange_order_id="exchange_order_1"
    )

    filled_order = DCAOrder(
        id=uuid.uuid4(),
        group_id=group_id,
        pyramid_id=uuid.uuid4(),
        leg_index=1,
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        price=Decimal("59000"),
        quantity=Decimal("0.001"),
        gap_percent=Decimal("-1"),
        weight_percent=Decimal("20"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("59590"),
        status=OrderStatus.FILLED.value,
        exchange_order_id="exchange_order_2",
        filled_quantity=Decimal("0.001"),
        tp_order_id="tp_order_1"
    )

    mock_dca_order_repository.get_all_orders_by_group_id.return_value = [open_order, filled_order]
    mock_exchange_connector.cancel_order.return_value = {"id": "order", "status": "canceled"}

    await order_service.cancel_open_orders_for_group(group_id)

    # Should cancel open order and TP order
    assert mock_exchange_connector.cancel_order.call_count >= 1

    # CRITICAL: Verify DB status was updated (catches "after hedge" bug)
    assert open_order.status == OrderStatus.CANCELLED.value, \
        "Open order must have CANCELLED status after cancel_open_orders_for_group"

    # Verify repository.update was called to persist the status change
    assert mock_dca_order_repository.update.call_count >= 1, \
        "Repository update must be called to persist status change"


@pytest.mark.asyncio
async def test_close_position_market_long(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test closing a long position with market order."""
    from app.models.position_group import PositionGroup

    position_group = MagicMock(spec=PositionGroup)
    position_group.id = uuid.uuid4()
    position_group.user_id = uuid.uuid4()
    position_group.side = "long"
    position_group.symbol = "BTC/USDT"
    position_group.exchange = "binance"

    mock_exchange_connector.place_order.return_value = {
        "id": "close_order_123",
        "status": "closed",
        "filled": 0.1,
        "average": 60000
    }

    await order_service.close_position_market(
        position_group=position_group,
        quantity_to_close=Decimal("0.1")
    )

    # Verify order was placed
    mock_exchange_connector.place_order.assert_awaited_once()

    # For long, close side should be SELL
    call_args = mock_exchange_connector.place_order.call_args
    assert call_args.kwargs.get("side", "").upper() == "SELL"
    assert call_args.kwargs.get("order_type", "").upper() == "MARKET"
    qty = call_args.kwargs.get("amount") or call_args.kwargs.get("quantity")
    assert qty == Decimal("0.1")
    assert call_args.kwargs.get("symbol") == "BTC/USDT"


@pytest.mark.asyncio
async def test_close_position_market_short(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test closing a short position with market order."""
    from app.models.position_group import PositionGroup

    position_group = MagicMock(spec=PositionGroup)
    position_group.id = uuid.uuid4()
    position_group.user_id = uuid.uuid4()
    position_group.side = "short"
    position_group.symbol = "BTC/USDT"
    position_group.exchange = "binance"

    mock_exchange_connector.place_order.return_value = {
        "id": "close_order_123",
        "status": "closed",
        "filled": 0.1,
        "average": 60000
    }

    await order_service.close_position_market(
        position_group=position_group,
        quantity_to_close=Decimal("0.1")
    )

    # Verify order was placed
    mock_exchange_connector.place_order.assert_awaited_once()

    # For short, close side should be BUY
    call_args = mock_exchange_connector.place_order.call_args
    assert call_args.kwargs.get("side", "").upper() == "BUY"
    assert call_args.kwargs.get("order_type", "").upper() == "MARKET"
    qty = call_args.kwargs.get("amount") or call_args.kwargs.get("quantity")
    assert qty == Decimal("0.1")


@pytest.mark.asyncio
async def test_execute_force_close_success(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test successful force close initiation."""
    from app.models.position_group import PositionGroup, PositionGroupStatus
    from app.repositories.position_group import PositionGroupRepository

    group_id = uuid.uuid4()
    user_id = order_service.user.id

    mock_position_group = MagicMock(spec=PositionGroup)
    mock_position_group.id = group_id
    mock_position_group.user_id = user_id
    mock_position_group.status = PositionGroupStatus.ACTIVE.value

    # Mock the repository
    mock_position_repo = AsyncMock()
    mock_position_repo.get.return_value = mock_position_group
    mock_position_repo.update = AsyncMock()
    order_service.position_group_repository = mock_position_repo

    result = await order_service.execute_force_close(group_id)

    # CRITICAL: Verify status transition happened
    assert result.status == PositionGroupStatus.CLOSING.value, \
        "Position must transition to CLOSING status on force close"

    # Verify repository update was called to persist the state change
    mock_position_repo.update.assert_awaited_once()

    # Verify the correct position was updated
    updated_position = mock_position_repo.update.call_args[0][0]
    assert updated_position.id == group_id
    assert updated_position.status == PositionGroupStatus.CLOSING.value


@pytest.mark.asyncio
async def test_execute_force_close_not_found(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test force close for non-existent position."""
    group_id = uuid.uuid4()

    mock_position_repo = AsyncMock()
    mock_position_repo.get.return_value = None
    order_service.position_group_repository = mock_position_repo

    with pytest.raises(APIError, match="not found"):
        await order_service.execute_force_close(group_id)


@pytest.mark.asyncio
async def test_execute_force_close_unauthorized(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test force close for position owned by another user."""
    from app.models.position_group import PositionGroup, PositionGroupStatus

    group_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    mock_position_group = MagicMock(spec=PositionGroup)
    mock_position_group.id = group_id
    mock_position_group.user_id = other_user_id  # Different user
    mock_position_group.status = PositionGroupStatus.ACTIVE.value

    mock_position_repo = AsyncMock()
    mock_position_repo.get.return_value = mock_position_group
    order_service.position_group_repository = mock_position_repo

    with pytest.raises(APIError, match="Not authorized"):
        await order_service.execute_force_close(group_id)


@pytest.mark.asyncio
async def test_execute_force_close_already_closed(order_service, mock_exchange_connector, mock_dca_order_repository):
    """Test force close for already closed position."""
    from app.models.position_group import PositionGroup, PositionGroupStatus

    group_id = uuid.uuid4()
    user_id = order_service.user.id

    mock_position_group = MagicMock(spec=PositionGroup)
    mock_position_group.id = group_id
    mock_position_group.user_id = user_id
    mock_position_group.status = PositionGroupStatus.CLOSED.value  # Already closed

    mock_position_repo = AsyncMock()
    mock_position_repo.get.return_value = mock_position_group
    order_service.position_group_repository = mock_position_repo

    with pytest.raises(APIError, match="already closed"):
        await order_service.execute_force_close(group_id)