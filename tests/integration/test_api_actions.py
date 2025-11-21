import pytest
from httpx import AsyncClient
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User
from app.schemas.position_group import PositionGroupSchema

@pytest.mark.asyncio
async def test_force_close_position(
    authorized_client: AsyncClient,
    test_user: User,
    db_session,
):
    # Create an active position that we will try to force close
    active_position = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        total_dca_legs=1,
        filled_dca_legs=0,
        base_entry_price=Decimal("1000"),
        weighted_avg_entry=Decimal("1000"),
        total_invested_usd=Decimal("100"),
        realized_pnl_usd=Decimal("0"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        closed_at=None
    )

    db_session.add(active_position)
    await db_session.commit()
    await db_session.refresh(active_position)

    # Attempt to force close the position
    response = await authorized_client.post(f"/api/v1/positions/{active_position.id}/close")

    assert response.status_code == 200

    # Verify the position status has transitioned to CLOSING in the database
    await db_session.refresh(active_position)
    assert active_position.status == PositionGroupStatus.CLOSING.value

    response_data = response.json()
    assert response_data["id"] == str(active_position.id)
    assert response_data["status"] == PositionGroupStatus.CLOSING.value

    # Test with a non-existent position
    non_existent_uuid = UUID('12345678-1234-5678-1234-567812345678')
    response_non_existent = await authorized_client.post(f"/api/v1/positions/{non_existent_uuid}/close")
    assert response_non_existent.status_code == 404

    # Test with a closed position (should not be allowed to force close again)
    closed_position = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="LTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.CLOSED.value,
        total_dca_legs=1,
        filled_dca_legs=0,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_invested_usd=Decimal("50"),
        realized_pnl_usd=Decimal("10"),
        unrealized_pnl_usd=Decimal("0"),
        unrealized_pnl_percent=Decimal("0"),
        tp_mode="per_leg",
        pyramid_count=0,
        max_pyramids=5,
        closed_at=datetime.utcnow()
    )
    db_session.add(closed_position)
    await db_session.commit()
    await db_session.refresh(closed_position)

    response_closed = await authorized_client.post(f"/api/v1/positions/{closed_position.id}/close")
    assert response_closed.status_code == 400 # Expecting a Bad Request or similar, as it's already closed
