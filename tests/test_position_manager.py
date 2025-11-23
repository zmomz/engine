import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from contextlib import asynccontextmanager

from unittest.mock import AsyncMock, MagicMock, patch

from app.services.position_manager import PositionManagerService
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.user import User # Import User model
from app.repositories.position_group import PositionGroupRepository
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig, DCALevelConfig
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService
from app.models.dca_order import DCAOrder, OrderStatus

# --- Fixtures for PositionManagerService --- 

@pytest.fixture
async def user_id_fixture(db_session: AsyncMock): # Use AsyncMock for db_session
    user = User(
        id=uuid.uuid4(),
        username="testuser_pm",
        email="test_pm@example.com",
        hashed_password="hashedpassword",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id



@pytest.fixture
def mock_grid_calculator_service():
    mock = MagicMock(spec=GridCalculatorService)
    mock.calculate_dca_levels.return_value = [
        {"leg_index": 0, "price": Decimal("100"), "quantity": Decimal("1"), "gap_percent": Decimal("0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("1"), "tp_price": Decimal("101")}
    ]
    mock.calculate_order_quantities.return_value = [
        {"leg_index": 0, "price": Decimal("100"), "quantity": Decimal("1"), "gap_percent": Decimal("0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("1"), "tp_price": Decimal("101")}
    ]
    return mock



@pytest.fixture
def mock_order_service_class():
    mock_instance = MagicMock(spec=OrderService)
    mock_instance.cancel_open_orders_for_group = AsyncMock()
    mock_instance.close_position_market = AsyncMock()
    mock_class = MagicMock(spec=OrderService, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_position_group_repository_class():
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.get_by_id = AsyncMock()
    mock_instance.create = AsyncMock()
    mock_instance.update = AsyncMock()
    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    return AsyncMock()

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def mock_session_factory(mock_db_session):
    @asynccontextmanager
    async def factory():
        yield mock_db_session
    return factory

@pytest.fixture
async def position_manager_service(
    mock_session_factory,
    mock_position_group_repository_class,
    mock_grid_calculator_service,
    mock_order_service_class,
    mock_exchange_connector,
    user_id_fixture,
    mock_db_session 
):
    # Configure mock_db_session to return a dummy user
    user = User(
        id=user_id_fixture,
        username="testuser_pm_service",
        email="test_pm_service@example.com",
        hashed_password="hashedpassword",
        exchange="mock",
        webhook_secret="mock_secret"
    )
    mock_db_session.get.return_value = user
    
    return PositionManagerService(
        session_factory=mock_session_factory, 
        user=user, 
        position_group_repository_class=mock_position_group_repository_class,
        grid_calculator_service=mock_grid_calculator_service,
        order_service_class=mock_order_service_class,
        exchange_connector=mock_exchange_connector
    )

# --- Test Data ---

@pytest.fixture
def sample_queued_signal(user_id_fixture):
    return QueuedSignal(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        entry_price=Decimal("100"),
        signal_payload={},
        status=QueueStatus.QUEUED
    )

@pytest.fixture
def sample_risk_config():
    return RiskEngineConfig(
        loss_threshold_percent=Decimal("-5.0"),
        require_full_pyramids=True,
        timer_start_condition="after_all_dca_filled",
        post_full_wait_minutes=60,
        max_winners_to_combine=3
    )

@pytest.fixture
def sample_dca_grid_config():
    return DCAGridConfig.model_validate([
        {"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 1.0}
    ])

@pytest.fixture
def sample_total_capital_usd():
    return Decimal("1000")

@pytest.fixture
def sample_position_group(sample_risk_config, user_id_fixture):
    pg = PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("10"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        replacement_count=0,
        risk_timer_start=datetime.utcnow() - timedelta(minutes=30),
        risk_timer_expires=datetime.utcnow() + timedelta(minutes=30)
    )
    return pg

# --- Tests --- 

@pytest.mark.asyncio
async def test_create_position_group_from_signal_new_position(
    position_manager_service,
    mock_db_session, 
    mock_position_group_repository_class,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd
):
    """Test creating a new PositionGroup from a queued signal with correct timer settings."""
    mock_user = MagicMock(spec=User)
    mock_user.encrypted_api_keys = {'data': 'test'}
    mock_db_session.get.return_value = mock_user 

    with patch('app.services.position_manager.get_exchange_connector') as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={})
        mock_get_connector.return_value = mock_connector

        created_pg = await position_manager_service.create_position_group_from_signal(
            session=mock_db_session, 
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )

    assert isinstance(created_pg, PositionGroup)
    assert created_pg.user_id == sample_queued_signal.user_id
    assert created_pg.symbol == sample_queued_signal.symbol
    assert created_pg.status == PositionGroupStatus.LIVE
    assert created_pg.risk_timer_start is not None
    assert created_pg.risk_timer_expires is not None
    expected_expiry = created_pg.risk_timer_start + timedelta(minutes=sample_risk_config.post_full_wait_minutes)
    assert abs((created_pg.risk_timer_expires - expected_expiry).total_seconds()) < 1 # Allow for minor time differences

@pytest.mark.asyncio
async def test_create_position_group_submits_orders(
    position_manager_service,
    mock_db_session, 
    mock_order_service_class,
    mock_grid_calculator_service,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd
):
    """Test that creating a position group also creates and submits DCA orders."""
    # Arrange
    mock_user = MagicMock(spec=User)
    mock_user.encrypted_api_keys = {'data': 'test'}
    mock_db_session.get.return_value = mock_user 

    dca_levels = [
        {"price": Decimal("100"), "quantity": Decimal("1.0"), "gap_percent": Decimal("1"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1"), "tp_price": Decimal("101")},
        {"price": Decimal("98"), "quantity": Decimal("1.2"), "gap_percent": Decimal("2"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1"), "tp_price": Decimal("99")}
    ]
    mock_grid_calculator_service.calculate_order_quantities.return_value = dca_levels
    
    with patch('app.services.position_manager.get_exchange_connector') as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={})
        mock_get_connector.return_value = mock_connector

        # Act
        await position_manager_service.create_position_group_from_signal(
            session=mock_db_session, 
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )
    
    # Assert
    mock_order_service_instance = mock_order_service_class.return_value
    assert mock_order_service_instance.submit_order.call_count == 2
    
    # Check the details of the first call
    first_call_args = mock_order_service_instance.submit_order.call_args_list[0].args
    dca_order_arg = first_call_args[0]
    
    assert isinstance(dca_order_arg, DCAOrder)
    assert dca_order_arg.price == dca_levels[0]['price']
    assert dca_order_arg.quantity == dca_levels[0]['quantity']
    assert dca_order_arg.status == OrderStatus.PENDING

@pytest.mark.asyncio
async def test_handle_pyramid_continuation_increment_count(
    position_manager_service,
    mock_db_session, 
    mock_position_group_repository_class,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd,
    sample_position_group
):
    """Test handling a pyramid continuation increments pyramid_count and replacement_count."""
    mock_user = MagicMock(spec=User)
    mock_user.encrypted_api_keys = {'data': 'test'}
    mock_db_session.get.return_value = mock_user 

    initial_pyramid_count = sample_position_group.pyramid_count
    initial_replacement_count = sample_position_group.replacement_count

    with patch('app.services.position_manager.get_exchange_connector') as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={})
        mock_get_connector.return_value = mock_connector

        updated_pg = await position_manager_service.handle_pyramid_continuation(
            session=mock_db_session, 
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            existing_position_group=sample_position_group,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )

    assert updated_pg.pyramid_count == initial_pyramid_count + 1
    assert updated_pg.replacement_count == initial_replacement_count + 1

@pytest.mark.asyncio
async def test_handle_pyramid_continuation_reset_timer(
    position_manager_service,
    mock_db_session, 
    mock_position_group_repository_class,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd,
    sample_position_group
):
    """Test handling a pyramid continuation resets the timer when configured."""
    mock_user = MagicMock(spec=User)
    mock_user.encrypted_api_keys = {'data': 'test'}
    mock_db_session.get.return_value = mock_user 

    sample_risk_config.reset_timer_on_replacement = True # Set config to reset timer
    initial_timer_expires = sample_position_group.risk_timer_expires

    with patch('app.services.position_manager.get_exchange_connector') as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={})
        mock_get_connector.return_value = mock_connector

        updated_pg = await position_manager_service.handle_pyramid_continuation(
            session=mock_db_session, 
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            existing_position_group=sample_position_group,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )

    assert updated_pg.risk_timer_start is not None
    assert updated_pg.risk_timer_expires is not None
    expected_expiry = updated_pg.risk_timer_start + timedelta(minutes=sample_risk_config.post_full_wait_minutes)
    assert abs((updated_pg.risk_timer_expires - expected_expiry).total_seconds()) < 1

@pytest.mark.asyncio
async def test_handle_pyramid_continuation_no_reset_timer(
    position_manager_service,
    mock_db_session, 
    mock_position_group_repository_class,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd,
    sample_position_group
):
    """Test handling a pyramid continuation does not reset the timer when not configured."""
    mock_user = MagicMock(spec=User)
    mock_user.encrypted_api_keys = {'data': 'test'}
    mock_db_session.get.return_value = mock_user 

    sample_risk_config.reset_timer_on_replacement = False # Set config to NOT reset timer
    initial_timer_start = sample_position_group.risk_timer_start
    initial_timer_expires = sample_position_group.risk_timer_expires

    with patch('app.services.position_manager.get_exchange_connector') as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.get_precision_rules = AsyncMock(return_value={})
        mock_get_connector.return_value = mock_connector

        updated_pg = await position_manager_service.handle_pyramid_continuation(
            session=mock_db_session, 
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            existing_position_group=sample_position_group,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )

    assert updated_pg.risk_timer_start == initial_timer_start # Timer should NOT have been reset
    assert updated_pg.risk_timer_expires == initial_timer_expires # Timer should NOT have been reset


# --- Exit Logic Test ---

@pytest.mark.asyncio
async def test_handle_exit_signal(
    position_manager_service, 
    mock_order_service_class,
    sample_position_group
):
    """
    Test that handle_exit_signal cancels open orders and closes the filled position.
    """
    # Add some orders to the position group
    filled_order = DCAOrder(status=OrderStatus.FILLED, filled_quantity=Decimal("1.5"))
    open_order = DCAOrder(status=OrderStatus.OPEN, filled_quantity=Decimal("0"))
    sample_position_group.dca_orders = [filled_order, open_order]
    
    await position_manager_service.handle_exit_signal(sample_position_group)

    # Get the mock instance that was created inside the method
    # In this setup, the instance is the same as the one returned by the class mock
    mock_order_service_instance = mock_order_service_class.return_value
    
    # Assert that open orders were cancelled
    mock_order_service_instance.cancel_open_orders_for_group.assert_called_once_with(sample_position_group.id)
    
    # Assert that the market close order was placed for the correct quantity
    mock_order_service_instance.close_position_market.assert_called_once_with(
        position_group=sample_position_group,
        quantity_to_close=Decimal("1.5")
    )


@pytest.mark.asyncio
async def test_risk_timer_start_after_5_pyramids(position_manager_service, mock_position_group_repository_class, user_id_fixture):
    """
    Test that the risk timer starts correctly when the 'after_5_pyramids'
    condition is met.
    """
    # Arrange
    now = datetime.utcnow()
    config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-5.0"),
        max_winners_to_combine=3,
        timer_start_condition="after_5_pyramids",
        post_full_wait_minutes=60
    )
    
    position_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=5,
        max_pyramids=5,
        total_dca_legs=5,
        base_entry_price=Decimal(100),
        weighted_avg_entry=Decimal(100),
        tp_mode="per_leg"
    )
    position_manager_service.position_group_repository_class.return_value.get_by_id.return_value = position_group

    # Act
    await position_manager_service.update_risk_timer(position_group.id, config)

    # Assert
    mock_position_group_repository_class.return_value.update.assert_called_once()
    updated_pg = mock_position_group_repository_class.return_value.update.call_args[0][0]
    assert updated_pg.risk_timer_expires is not None
    expected_expiry = now + timedelta(minutes=60)
    assert updated_pg.risk_timer_expires > now
    assert updated_pg.risk_timer_expires < expected_expiry + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_risk_timer_start_after_all_dca_submitted(position_manager_service, mock_position_group_repository_class, user_id_fixture):
    """
    Test that the risk timer starts correctly when the 'after_all_dca_submitted'
    condition is met.
    """
    # Arrange
    now = datetime.utcnow()
    config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-5.0"),
        max_winners_to_combine=3,
        timer_start_condition="after_all_dca_submitted",
        post_full_wait_minutes=30
    )
    
    position_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=60,
        side="short",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=5,
        max_pyramids=5,
        total_dca_legs=3,
        filled_dca_legs=2, # Not all filled
        base_entry_price=Decimal(2000),
        weighted_avg_entry=Decimal(2000),
        tp_mode="aggregate"
    )
    position_manager_service.position_group_repository_class.return_value.get_by_id.return_value = position_group

    # Act
    await position_manager_service.update_risk_timer(position_group.id, config)

    # Assert
    mock_position_group_repository_class.return_value.update.assert_called_once()
    updated_pg = mock_position_group_repository_class.return_value.update.call_args[0][0]
    assert updated_pg.risk_timer_expires is not None
    expected_expiry = now + timedelta(minutes=30)
    assert updated_pg.risk_timer_expires > now
    assert updated_pg.risk_timer_expires < expected_expiry + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_risk_timer_start_after_all_dca_filled(position_manager_service, mock_position_group_repository_class, user_id_fixture):
    """
    Test that the risk timer starts correctly when the 'after_all_dca_filled'
    condition is met.
    """
    # Arrange
    now = datetime.utcnow()
    config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-5.0"),
        max_winners_to_combine=3,
        timer_start_condition="after_all_dca_filled",
        post_full_wait_minutes=15
    )
    
    position_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance",
        symbol="SOLUSDT",
        timeframe=5,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=5,
        max_pyramids=5,
        total_dca_legs=4,
        filled_dca_legs=4, # All filled
        base_entry_price=Decimal(50),
        weighted_avg_entry=Decimal(50),
        tp_mode="hybrid"
    )
    position_manager_service.position_group_repository_class.return_value.get_by_id.return_value = position_group

    # Act
    await position_manager_service.update_risk_timer(position_group.id, config)

    # Assert
    mock_position_group_repository_class.return_value.update.assert_called_once()
    updated_pg = mock_position_group_repository_class.return_value.update.call_args[0][0]
    assert updated_pg.risk_timer_expires is not None
    expected_expiry = now + timedelta(minutes=15)
    assert updated_pg.risk_timer_expires > now
    assert updated_pg.risk_timer_expires < expected_expiry + timedelta(seconds=1)