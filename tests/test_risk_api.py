import pytest
from httpx import AsyncClient
import uuid
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from datetime import datetime

from app.main import app
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.schemas.position_group import TPMode
from app.services.risk_engine import RiskEngineService
from app.api.risk import get_risk_engine_service
from app.db.database import AsyncSession

# Use the mock_async_session from conftest
from .conftest import mock_async_session

@pytest.fixture
def mock_risk_engine_service():
    return AsyncMock(spec=RiskEngineService)

@pytest.fixture(autouse=True)
def override_dependencies(mock_risk_engine_service: RiskEngineService):
    app.dependency_overrides[get_risk_engine_service] = lambda: mock_risk_engine_service
    yield
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_block_risk_for_group_success(mock_risk_engine_service: RiskEngineService):
    """Test successfully blocking risk for a group."""
    group_id = uuid.uuid4()
    mock_pg = PositionGroup(
        id=group_id,
        user_id=uuid.uuid4(),
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
        risk_blocked=True,
        risk_skip_once=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    mock_risk_engine_service.set_risk_blocked.return_value = mock_pg

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/risk/{group_id}/block")

    assert response.status_code == 200
    mock_risk_engine_service.set_risk_blocked.assert_called_once_with(group_id, True)
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["risk_blocked"] is True

@pytest.mark.asyncio
async def test_unblock_risk_for_group_success(mock_risk_engine_service: RiskEngineService):
    """Test successfully unblocking risk for a group."""
    group_id = uuid.uuid4()
    mock_pg = PositionGroup(
        id=group_id,
        user_id=uuid.uuid4(),
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
    mock_risk_engine_service.set_risk_blocked.return_value = mock_pg

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/risk/{group_id}/unblock")

    assert response.status_code == 200
    mock_risk_engine_service.set_risk_blocked.assert_called_once_with(group_id, False)
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["risk_blocked"] is False

@pytest.mark.asyncio
async def test_skip_next_risk_evaluation_success(mock_risk_engine_service: RiskEngineService):
    """Test successfully skipping the next risk evaluation for a group."""
    group_id = uuid.uuid4()
    mock_pg = PositionGroup(
        id=group_id,
        user_id=uuid.uuid4(),
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
        risk_skip_once=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    mock_risk_engine_service.set_risk_skip_once.return_value = mock_pg

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/risk/{group_id}/skip")

    assert response.status_code == 200
    mock_risk_engine_service.set_risk_skip_once.assert_called_once_with(group_id, True)
    response_data = response.json()
    assert response_data["id"] == str(group_id)
    assert response_data["risk_skip_once"] is True
