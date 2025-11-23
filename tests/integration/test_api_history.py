import pytest
from httpx import AsyncClient
from uuid import UUID
from datetime import datetime

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from decimal import Decimal

@pytest.mark.asyncio
async def test_get_position_history(
    authorized_client: AsyncClient,
    test_user: User,
    db_session,
):
    # Create some historical (closed) positions
    closed_position_1 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.CLOSED.value,
        total_dca_legs=1,
        filled_dca_legs=0,
        base_entry_price=Decimal("1000"),
        weighted_avg_entry=Decimal("1000"),
        total_invested_usd=Decimal("100"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("10"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        closed_at=datetime.utcnow()
    )
    closed_position_2 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="ETHUSDT",
        timeframe=15,
        side="short",
        status=PositionGroupStatus.CLOSED.value,
        total_dca_legs=1,
        filled_dca_legs=0,
        base_entry_price=Decimal("500"),
        weighted_avg_entry=Decimal("500"),
        total_invested_usd=Decimal("50"),
            unrealized_pnl_usd=Decimal("0"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("-5"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        closed_at=datetime.utcnow()
    )
    # Create an active position (should not be returned by history endpoint)
    active_position = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="ADAUSDT",
        timeframe=30,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        total_dca_legs=1,
        filled_dca_legs=0,
        base_entry_price=Decimal("2000"),
        weighted_avg_entry=Decimal("2000"),
        total_invested_usd=Decimal("200"),
            unrealized_pnl_usd=Decimal("5"),
            unrealized_pnl_percent=Decimal("0"),
            realized_pnl_usd=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        closed_at=None
    )
    db_session.add(closed_position_1)
    db_session.add(closed_position_2)
    db_session.add(active_position)
    await db_session.commit()
    await db_session.refresh(closed_position_1)
    await db_session.refresh(closed_position_2)
    await db_session.refresh(active_position)

    response = await authorized_client.get(f"/api/v1/positions/{test_user.id}/history")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    symbols_in_history = {p["symbol"] for p in data}
    assert "BTCUSDT" in symbols_in_history
    assert "ETHUSDT" in symbols_in_history
    assert "ADAUSDT" not in symbols_in_history

    # Verify content of a closed position
    for pos in data:
        if pos["symbol"] == "BTCUSDT":
            assert pos["status"] == PositionGroupStatus.CLOSED.value
            assert UUID(pos["user_id"]) == test_user.id
            assert Decimal(pos["realized_pnl_usd"]) == Decimal("10")
            assert pos["closed_at"] is not None
        elif pos["symbol"] == "ETHUSDT":
            assert pos["status"] == PositionGroupStatus.CLOSED.value
            assert UUID(pos["user_id"]) == test_user.id
            assert Decimal(pos["realized_pnl_usd"]) == Decimal("-5")
            assert pos["closed_at"] is not None
