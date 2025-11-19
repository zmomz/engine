import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import uuid

from app.services.risk_engine import RiskEngineService
from app.models.queued_signal import QueuedSignal
from app.models.position_group import PositionGroup
from app.schemas.grid_config import RiskEngineConfig

@pytest.fixture
def mock_risk_engine_service():
    risk_config = RiskEngineConfig(
        max_open_positions_global=2,
        max_open_positions_per_symbol=1,
        max_total_exposure_usd=Decimal("1000")
    )
    # Mock dependencies
    session_factory = MagicMock()
    position_group_repo = MagicMock()
    risk_action_repo = MagicMock()
    dca_order_repo = MagicMock()
    exchange_connector = AsyncMock()
    order_service = MagicMock()

    service = RiskEngineService(
        session_factory=session_factory,
        position_group_repository_class=position_group_repo,
        risk_action_repository_class=risk_action_repo,
        dca_order_repository_class=dca_order_repo,
        exchange_connector=exchange_connector,
        order_service_class=order_service,
        risk_engine_config=risk_config
    )
    return service

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pass(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long")
    active_positions = [] # No active positions
    allocated_capital = Decimal("100")

    result = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital
    )
    assert result is True

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_max_global(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long")
    # Mock 2 active positions (limit is 2, so 3rd should fail)
    active_positions = [
        PositionGroup(symbol="ETHUSDT", total_invested_usd=Decimal("100")),
        PositionGroup(symbol="SOLUSDT", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")

    result = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_max_symbol(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long")
    # Mock 1 active position for BTCUSDT (limit is 1)
    active_positions = [
        PositionGroup(symbol="BTCUSDT", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")

    result = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital
    )
    assert result is False

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_pass_pyramid(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long")
    # Mock 1 active position for BTCUSDT (limit is 1)
    active_positions = [
        PositionGroup(symbol="BTCUSDT", total_invested_usd=Decimal("100"))
    ]
    allocated_capital = Decimal("100")

    # Should pass because it is a pyramid continuation
    result = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital, is_pyramid_continuation=True
    )
    assert result is True

@pytest.mark.asyncio
async def test_validate_pre_trade_risk_fail_exposure(mock_risk_engine_service):
    signal = QueuedSignal(symbol="BTCUSDT", side="long")
    # Mock active positions with 900 exposure (limit is 1000)
    active_positions = [
        PositionGroup(symbol="ETHUSDT", total_invested_usd=Decimal("900"))
    ]
    # Requesting 200 more would exceed 1000
    allocated_capital = Decimal("200")

    result = await mock_risk_engine_service.validate_pre_trade_risk(
        signal, active_positions, allocated_capital
    )
    assert result is False