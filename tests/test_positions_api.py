import pytest
from httpx import AsyncClient
import uuid
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from datetime import datetime

from app.main import app
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.position_group import TPMode
from app.repositories.position_group import PositionGroupRepository
from app.db.database import get_db_session, AsyncSession

# Use the mock_async_session from conftest
from .conftest import mock_async_session

@pytest.fixture
def position_group_repository(mock_async_session: AsyncSession):
    return PositionGroupRepository(mock_async_session)

@pytest.fixture(autouse=True)
def override_dependencies(mock_async_session: AsyncSession):
    async def get_session_override():
        yield mock_async_session

    app.dependency_overrides[get_db_session] = get_session_override
    yield
    app.dependency_overrides = {}


from app.api.dependencies.users import get_current_active_user
from app.models.user import User

@pytest.mark.asyncio
async def test_get_all_positions_success(mock_async_session: AsyncSession):
    """Test successfully retrieving all active position groups for a user."""
    user_id = uuid.uuid4()
    mock_user = User(id=user_id, username="test", email="test@test.com", hashed_password="hash")
    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    mock_positions = [
        PositionGroup(
            id=uuid.uuid4(),
            user_id=user_id,
            exchange="binance",
            symbol="BTCUSDT",
            timeframe=15,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=1,
            max_pyramids=5,
            total_dca_legs=5,
            filled_dca_legs=1,
            base_entry_price=Decimal("50000.00"),
            weighted_avg_entry=Decimal("50000.00"),
            total_invested_usd=Decimal("1000"),
            total_filled_quantity=Decimal("0.02"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.PER_LEG,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        PositionGroup(
            id=uuid.uuid4(),
            user_id=user_id,
            exchange="bybit",
            symbol="ETHUSDT",
            timeframe=60,
            side="short",
            status=PositionGroupStatus.ACTIVE,
            pyramid_count=1,
            max_pyramids=5,
            total_dca_legs=3,
            filled_dca_legs=1,
            base_entry_price=Decimal("3000.00"),
            weighted_avg_entry=Decimal("3000.00"),
            total_invested_usd=Decimal("500"),
            total_filled_quantity=Decimal("0.1"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
            tp_mode=TPMode.AGGREGATE,
            risk_eligible=False,
            risk_blocked=False,
            risk_skip_once=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_positions
    mock_async_session.execute.return_value = mock_result

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/positions/{user_id}")

    del app.dependency_overrides[get_current_active_user]
    assert response.status_code == 200
    mock_async_session.execute.assert_called_once()
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["symbol"] == "BTCUSDT"
    assert response_data[1]["symbol"] == "ETHUSDT"

@pytest.mark.asyncio
async def test_get_position_group_success(mock_async_session: AsyncSession):
    """Test successfully retrieving a specific position group for a user."""
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    mock_user = User(id=user_id, username="test", email="test@test.com", hashed_password="hash")
    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    mock_position = PositionGroup(
        id=group_id,
        user_id=user_id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=15,
        side="long",
        status=PositionGroupStatus.ACTIVE,
        pyramid_count=1,
        max_pyramids=5,
        total_dca_legs=5,
        filled_dca_legs=1,
        base_entry_price=Decimal("50000.00"),
        weighted_avg_entry=Decimal("50000.00"),
        total_invested_usd=Decimal("1000"),
        total_filled_quantity=Decimal("0.02"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
        tp_mode=TPMode.PER_LEG,
        risk_eligible=False,
        risk_blocked=False,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_position
    mock_async_session.execute.return_value = mock_result

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/positions/{user_id}/{group_id}")

    del app.dependency_overrides[get_current_active_user]
    assert response.status_code == 200
    mock_async_session.execute.assert_called_once()
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["symbol"] == "BTCUSDT"

@pytest.mark.asyncio
async def test_get_position_group_not_found(mock_async_session: AsyncSession):
    """Test retrieving a non-existent position group."""
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    mock_user = User(id=user_id, username="test", email="test@test.com", hashed_password="hash")
    app.dependency_overrides[get_current_active_user] = lambda: mock_user
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_async_session.execute.return_value = mock_result

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/positions/{user_id}/{group_id}")

    del app.dependency_overrides[get_current_active_user]
    assert response.status_code == 404
    assert response.json() == {"detail": "Position group not found."}
