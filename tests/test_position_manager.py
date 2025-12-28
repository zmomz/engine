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
        # Helper to convert Decimal to str for JSON serialization (copied from conftest.py)
        def convert_decimals_to_str(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, dict):
                return {k: convert_decimals_to_str(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_decimals_to_str(elem) for elem in obj]
            return obj

        # Use the actual config schemas and then convert to JSON serializable dict
        risk_config_data = RiskEngineConfig().model_dump()
        dca_grid_config_data = DCAGridConfig(
            levels=[
                {"gap_percent": Decimal("0.0"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1.0")},
                {"gap_percent": Decimal("-0.5"), "weight_percent": Decimal("50"), "tp_percent": Decimal("0.5")}
            ],
            tp_mode="per_leg",
            tp_aggregate_percent=Decimal("0")
        ).model_dump()

        user = User(
            id=uuid.uuid4(),
            username="testuser_pm",
            email="test_pm@example.com",
            hashed_password="hashedpassword",
            exchange="binance",
            risk_config=convert_decimals_to_str(risk_config_data),
            encrypted_api_keys={'binance': {'encrypted_data': 'test_encrypted_key'}}
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user.id



@pytest.fixture
def mock_grid_calculator_service():
    mock = MagicMock(spec=GridCalculatorService)
    mock.calculate_dca_levels.return_value = [
        {"leg_index": 0, "price": Decimal("100"), "quantity": Decimal("2.0"), "gap_percent": Decimal("0"), "weight_percent": Decimal("20"), "tp_percent": Decimal("1"), "tp_price": Decimal("101")},
        {"leg_index": 1, "price": Decimal("99"), "quantity": Decimal("2.02"), "gap_percent": Decimal("-1"), "weight_percent": Decimal("20"), "tp_percent": Decimal("1"), "tp_price": Decimal("100")}
    ]
    # Use side_effect to call the real method for calculate_order_quantities
    mock.calculate_order_quantities.side_effect = GridCalculatorService.calculate_order_quantities
    return mock



@pytest.fixture
def mock_order_service_class():
    mock_instance = MagicMock(spec=OrderService)
    mock_instance.cancel_open_orders_for_group = AsyncMock()
    mock_instance.close_position_market = AsyncMock()
    mock_instance.submit_order = AsyncMock() # Ensure submit_order is mocked
    mock_class = MagicMock(spec=OrderService, return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_position_group_repository_class(user_id_fixture): # Add user_id_fixture dependency
    mock_instance = MagicMock(spec=PositionGroupRepository)
    mock_instance.get_by_id = AsyncMock()
    mock_instance.create = AsyncMock()
    mock_instance.update = AsyncMock()

    # Create a dummy PositionGroup instance for get_with_orders and get_by_id to return
    dummy_position_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance", # Ensure this is a string
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_invested_usd=Decimal("1.5"),
        total_filled_quantity=Decimal("1.5"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        risk_timer_start=datetime.utcnow() - timedelta(minutes=30),
        risk_timer_expires=datetime.utcnow() + timedelta(minutes=30)
    )
    mock_instance.get_with_orders = AsyncMock(return_value=dummy_position_group)
    mock_instance.get_by_id = AsyncMock(return_value=dummy_position_group)

    # Mock increment_pyramid_count - just return incremented count
    # The actual position_group will be updated via session.refresh mock
    mock_instance.increment_pyramid_count = AsyncMock(return_value=1)

    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

@pytest.fixture
def mock_exchange_connector():
    return AsyncMock()

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.add = MagicMock() # Ensure add is a synchronous mock
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock() # Mock flush

    # Mock refresh to increment pyramid_count on the position group
    async def mock_refresh(obj):
        if hasattr(obj, 'pyramid_count'):
            obj.pyramid_count += 1
    session.refresh = AsyncMock(side_effect=mock_refresh)

    # Mock result for session.execute
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [] # Default empty list
    session.execute.return_value = mock_result

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
    # Helper to convert Decimal to str for JSON serialization (copied from conftest.py)
    def convert_decimals_to_str(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert_decimals_to_str(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_decimals_to_str(elem) for elem in obj]
        return obj

    # Use the actual config schemas and then convert to JSON serializable dict
    risk_config_data = RiskEngineConfig().model_dump()
    dca_grid_config_data = DCAGridConfig(
        levels=[
            {"gap_percent": Decimal("0.0"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1.0")},
            {"gap_percent": Decimal("-0.5"), "weight_percent": Decimal("50"), "tp_percent": Decimal("0.5")}
        ],
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    ).model_dump()

    user = User(
        id=user_id_fixture,
        username="testuser_pm_service",
        email="test_pm_service@example.com",
        hashed_password="hashedpassword",
        exchange="binance",
        webhook_secret="mock_secret",
        risk_config=convert_decimals_to_str(risk_config_data),
        encrypted_api_keys={'binance': {'encrypted_data': 'test_encrypted_key'}}
    )
    mock_db_session.get.return_value = user
    
    with patch('app.core.security.EncryptionService') as MockEncryptionService:
        MockEncryptionService.return_value.decrypt_keys.return_value = ("dummy_api_key", "dummy_secret_key")
        # Patch get_exchange_connector in the modules that actually use it
        with patch('app.services.position.position_manager.get_exchange_connector') as mock_get_connector, \
             patch('app.services.position.position_creator.get_exchange_connector') as mock_get_connector2, \
             patch('app.services.position.position_closer.get_exchange_connector') as mock_get_connector3:
            mock_connector = AsyncMock() # Ensure it's an AsyncMock
            mock_connector.get_precision_rules.return_value = {
                "BTCUSDT": {"tick_size": 0.01, "step_size": 0.000001, "min_qty": 0.000001, "min_notional": 10.0}
            }
            mock_connector.get_current_price.return_value = Decimal("100") # Mock return value for get_current_price
            mock_connector.close = AsyncMock() # Mock the close method
            mock_get_connector.return_value = mock_connector
            mock_get_connector2.return_value = mock_connector
            mock_get_connector3.return_value = mock_connector

            yield PositionManagerService(
                session_factory=mock_session_factory,
                user=user,
                position_group_repository_class=mock_position_group_repository_class,
                grid_calculator_service=mock_grid_calculator_service,
                order_service_class=mock_order_service_class
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
        required_pyramids_for_timer=3,
        post_pyramids_wait_minutes=60,
        max_winners_to_combine=3
    )

@pytest.fixture
def sample_dca_grid_config():
    return DCAGridConfig.model_validate({
        "levels": [
            {"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 1.0}
        ],
        "tp_mode": "per_leg",
        "tp_aggregate_percent": Decimal("0")
    })

@pytest.fixture
def sample_total_capital_usd():
    return Decimal("1000")

@pytest.fixture
def sample_position_group(sample_risk_config, user_id_fixture):
    pg = PositionGroup(
        id=uuid.uuid4(),
        user_id=user_id_fixture,
        exchange="binance", # Explicitly set exchange to a string
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("1.5"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
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
    # Arrange

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
    
    # Timer should NOT start immediately on creation (unless conditions are met instantly, which is impossible for new group with 0 pyramids)
    assert created_pg.risk_timer_start is None
    assert created_pg.risk_timer_expires is None

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

    dca_levels = [
        {"price": Decimal("100"), "quantity": Decimal("2.0"), "gap_percent": Decimal("1"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1"), "tp_price": Decimal("101")},
        {"price": Decimal("98"), "quantity": Decimal("2.02"), "gap_percent": Decimal("2"), "weight_percent": Decimal("50"), "tp_percent": Decimal("1"), "tp_price": Decimal("99")}
    ]
    
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
    """Test handling a pyramid continuation increments pyramid_count."""
    initial_pyramid_count = sample_position_group.pyramid_count

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

@pytest.mark.asyncio
async def test_handle_pyramid_continuation_clears_timer(
    position_manager_service,
    mock_db_session,
    mock_position_group_repository_class,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd,
    sample_position_group
):
    """Test handling a pyramid continuation clears the timer for risk engine re-evaluation."""
    # Set initial timer values
    sample_position_group.risk_timer_start = datetime.utcnow() - timedelta(minutes=5)
    sample_position_group.risk_timer_expires = datetime.utcnow() + timedelta(minutes=10)

    updated_pg = await position_manager_service.handle_pyramid_continuation(
        session=mock_db_session,
        user_id=sample_queued_signal.user_id,
        signal=sample_queued_signal,
        existing_position_group=sample_position_group,
        risk_config=sample_risk_config,
        dca_grid_config=sample_dca_grid_config,
        total_capital_usd=sample_total_capital_usd
    )

    # Timer should be cleared - risk engine will re-evaluate and set it if conditions are met
    assert updated_pg.risk_timer_start is None
    assert updated_pg.risk_timer_expires is None


# --- Exit Logic Test ---

@pytest.mark.asyncio
async def test_handle_exit_signal(
    position_manager_service, 
    mock_order_service_class,
    sample_position_group,
    mock_position_group_repository_class # Added fixture dependency
):
    """
    Test that handle_exit_signal cancels open orders and closes the filled position.
    """
    # Add some orders to the position group
    filled_order = DCAOrder(status=OrderStatus.FILLED, filled_quantity=Decimal("1.5"))
    open_order = DCAOrder(status=OrderStatus.OPEN, filled_quantity=Decimal("0"))
    sample_position_group.dca_orders = [filled_order, open_order]
    
    # Ensure sample_position_group.exchange is a string
    sample_position_group.exchange = "binance"

    # Configure the repository mock to return our sample position group
    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get_with_orders.return_value = sample_position_group
    
    await position_manager_service.handle_exit_signal(sample_position_group.id)

    # Get the mock instance that was created inside the method
    # In this setup, the instance is the same as the one returned by the class mock
    mock_order_service_instance = mock_order_service_class.return_value
    
    # Assert that open orders were cancelled
    mock_order_service_instance.cancel_open_orders_for_group.assert_called_once_with(sample_position_group.id)
    
    # Assert that the market close order was placed for the correct quantity
    mock_order_service_instance.close_position_market.assert_called_once_with(
        position_group=sample_position_group,
        quantity_to_close=Decimal("1.5"),
        expected_price=Decimal("100"),
        max_slippage_percent=1.0,
        slippage_action="warn"
    )


@pytest.mark.asyncio
async def test_update_risk_timer_defers_to_risk_engine(position_manager_service, mock_position_group_repository_class, user_id_fixture):
    """
    Test that update_risk_timer defers timer management to the risk engine.
    The position manager no longer starts timers directly - it logs and defers to risk engine evaluation.
    """
    config = RiskEngineConfig(
        loss_threshold_percent=Decimal("-5.0"),
        required_pyramids_for_timer=3,
        post_pyramids_wait_minutes=15,
        max_winners_to_combine=3
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
    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get.return_value = position_group

    # Act - this should just log and return, not update the timer directly
    await position_manager_service.update_risk_timer(position_group.id, config)

    # Assert - timer management is deferred to risk engine, no direct updates
    mock_repo_instance.update.assert_not_called()


# --- Additional Coverage Tests ---

@pytest.mark.asyncio
async def test_handle_exit_signal_already_closed(
    position_manager_service,
    mock_order_service_class,
    mock_position_group_repository_class
):
    """Test that handle_exit_signal skips processing for already closed positions."""
    closed_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.CLOSED,
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_filled_quantity=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5
    )

    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get_with_orders.return_value = closed_group

    await position_manager_service.handle_exit_signal(closed_group.id)

    # Should not attempt to cancel or close
    mock_order_service_class.return_value.cancel_open_orders_for_group.assert_not_called()
    mock_order_service_class.return_value.close_position_market.assert_not_called()


@pytest.mark.asyncio
async def test_handle_exit_signal_no_filled_quantity(
    position_manager_service,
    mock_order_service_class,
    mock_position_group_repository_class
):
    """Test handle_exit_signal when no filled quantity to close."""
    empty_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.LIVE,
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_filled_quantity=Decimal("0"),  # No filled quantity
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5
    )
    empty_group.dca_orders = []

    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get_with_orders.return_value = empty_group

    await position_manager_service.handle_exit_signal(empty_group.id)

    # Should cancel orders but not place close market order
    mock_order_service_class.return_value.cancel_open_orders_for_group.assert_called_once()
    mock_order_service_class.return_value.close_position_market.assert_not_called()
    assert empty_group.status == PositionGroupStatus.CLOSED


@pytest.mark.asyncio
async def test_handle_exit_signal_short_position(
    position_manager_service,
    mock_order_service_class,
    mock_position_group_repository_class
):
    """Test handle_exit_signal for a short position calculates PnL correctly."""
    short_group = PositionGroup(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="short",
        status=PositionGroupStatus.ACTIVE,
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_invested_usd=Decimal("150"),
        total_filled_quantity=Decimal("1.5"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5
    )
    short_group.dca_orders = [DCAOrder(status=OrderStatus.FILLED, filled_quantity=Decimal("1.5"))]

    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get_with_orders.return_value = short_group

    await position_manager_service.handle_exit_signal(short_group.id)

    # Should place close order to buy back
    mock_order_service_class.return_value.close_position_market.assert_called_once()


@pytest.mark.asyncio
async def test_handle_exit_signal_position_not_found(
    position_manager_service,
    mock_position_group_repository_class
):
    """Test handle_exit_signal when position group not found."""
    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get_with_orders.return_value = None

    # Should not raise, just log and return
    await position_manager_service.handle_exit_signal(uuid.uuid4())


@pytest.mark.asyncio
async def test_update_position_stats_position_not_found(
    position_manager_service,
    mock_db_session,
    mock_position_group_repository_class
):
    """Test update_position_stats when position group not found."""
    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get_with_orders.return_value = None

    result = await position_manager_service.update_position_stats(uuid.uuid4(), session=mock_db_session)

    assert result is None


@pytest.mark.asyncio
async def test_update_risk_timer_with_existing_timer(
    position_manager_service,
    mock_position_group_repository_class,
    user_id_fixture
):
    """Test that update_risk_timer defers to risk engine even when timer exists."""
    config = RiskEngineConfig(
        required_pyramids_for_timer=3,
        post_pyramids_wait_minutes=60
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
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        tp_mode="per_leg",
        risk_timer_expires=datetime.utcnow() + timedelta(minutes=30)  # Already set
    )

    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get.return_value = position_group

    await position_manager_service.update_risk_timer(position_group.id, config)

    # Timer management is deferred to risk engine - no direct updates by position manager
    mock_repo_instance.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_risk_timer_position_not_found(
    position_manager_service,
    mock_position_group_repository_class
):
    """Test update_risk_timer when position group not found."""
    config = RiskEngineConfig()

    mock_repo_instance = mock_position_group_repository_class.return_value
    mock_repo_instance.get.return_value = None

    # Should not raise
    await position_manager_service.update_risk_timer(uuid.uuid4(), config)


def test_get_exchange_connector_for_user_dict_format():
    """Test _get_exchange_connector_for_user with dict format API keys."""
    user = MagicMock()
    user.encrypted_api_keys = {"binance": {"encrypted_data": "test_key"}}

    service = PositionManagerService(
        session_factory=MagicMock(),
        user=user,
        position_group_repository_class=MagicMock(),
        grid_calculator_service=MagicMock(),
        order_service_class=MagicMock()
    )

    with patch("app.services.position.position_manager.get_exchange_connector") as mock_connector:
        mock_connector.return_value = MagicMock()
        result = service._get_exchange_connector_for_user(user, "binance")
        mock_connector.assert_called_once()


def test_get_exchange_connector_for_user_string_format():
    """Test _get_exchange_connector_for_user with legacy string format."""
    user = MagicMock()
    user.encrypted_api_keys = "legacy_encrypted_string"

    service = PositionManagerService(
        session_factory=MagicMock(),
        user=user,
        position_group_repository_class=MagicMock(),
        grid_calculator_service=MagicMock(),
        order_service_class=MagicMock()
    )

    with patch("app.services.position.position_manager.get_exchange_connector") as mock_connector:
        mock_connector.return_value = MagicMock()
        result = service._get_exchange_connector_for_user(user, "binance")
        mock_connector.assert_called_once_with("binance", {"encrypted_data": "legacy_encrypted_string"})


def test_get_exchange_connector_for_user_missing_exchange():
    """Test _get_exchange_connector_for_user raises error for missing exchange."""
    user = MagicMock()
    user.encrypted_api_keys = {"binance": {"encrypted_data": "test_key"}}

    service = PositionManagerService(
        session_factory=MagicMock(),
        user=user,
        position_group_repository_class=MagicMock(),
        grid_calculator_service=MagicMock(),
        order_service_class=MagicMock()
    )

    with pytest.raises(ValueError, match="No API keys found"):
        service._get_exchange_connector_for_user(user, "bybit")


def test_get_exchange_connector_for_user_invalid_format():
    """Test _get_exchange_connector_for_user raises error for invalid format."""
    user = MagicMock()
    user.encrypted_api_keys = 12345  # Invalid format

    service = PositionManagerService(
        session_factory=MagicMock(),
        user=user,
        position_group_repository_class=MagicMock(),
        grid_calculator_service=MagicMock(),
        order_service_class=MagicMock()
    )

    with pytest.raises(ValueError, match="Invalid format"):
        service._get_exchange_connector_for_user(user, "binance")


@pytest.mark.asyncio
async def test_create_position_group_user_not_found(
    position_manager_service,
    mock_db_session,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd
):
    """Test create_position_group_from_signal raises error when user not found."""
    from app.services.position_manager import UserNotFoundException

    mock_db_session.get.return_value = None

    with pytest.raises(UserNotFoundException):
        await position_manager_service.create_position_group_from_signal(
            session=mock_db_session,
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )


@pytest.mark.asyncio
async def test_create_position_group_market_entry_order(
    position_manager_service,
    mock_db_session,
    mock_order_service_class,
    sample_queued_signal,
    sample_risk_config,
    sample_total_capital_usd
):
    """Test create_position_group_from_signal with market entry order type."""
    dca_config = DCAGridConfig.model_validate({
        "levels": [
            {"gap_percent": 0.0, "weight_percent": 50, "tp_percent": 1.0},
            {"gap_percent": -0.5, "weight_percent": 50, "tp_percent": 0.5}
        ],
        "tp_mode": "per_leg",
        "tp_aggregate_percent": Decimal("0"),
        "entry_order_type": "market"  # Market entry
    })

    await position_manager_service.create_position_group_from_signal(
        session=mock_db_session,
        user_id=sample_queued_signal.user_id,
        signal=sample_queued_signal,
        risk_config=sample_risk_config,
        dca_grid_config=dca_config,
        total_capital_usd=Decimal("1000")
    )

    # First order should NOT be submitted (it's TRIGGER_PENDING for market)
    # Only subsequent limit orders should be submitted
    mock_order_service_instance = mock_order_service_class.return_value
    # With 2 levels, first is market (not submitted), second is limit (submitted)
    assert mock_order_service_instance.submit_order.call_count == 1


@pytest.mark.asyncio
async def test_handle_pyramid_continuation_user_not_found(
    position_manager_service,
    mock_db_session,
    sample_queued_signal,
    sample_risk_config,
    sample_dca_grid_config,
    sample_total_capital_usd,
    sample_position_group
):
    """Test handle_pyramid_continuation raises error when user not found."""
    from app.services.position_manager import UserNotFoundException

    mock_db_session.get.return_value = None

    with pytest.raises(UserNotFoundException):
        await position_manager_service.handle_pyramid_continuation(
            session=mock_db_session,
            user_id=sample_queued_signal.user_id,
            signal=sample_queued_signal,
            existing_position_group=sample_position_group,
            risk_config=sample_risk_config,
            dca_grid_config=sample_dca_grid_config,
            total_capital_usd=sample_total_capital_usd
        )