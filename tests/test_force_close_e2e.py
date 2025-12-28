
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
import uuid
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.api.dependencies.users import get_current_active_user
from app.main import app

@pytest.mark.asyncio
async def test_force_close_position_e2e(authorized_client, test_user, db_session):
    """
    Tests the force close logic more end-to-end, without mocking the services.
    """
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="bybit",
        symbol="ETH/USDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        total_filled_quantity=Decimal("1"),
        base_entry_price=Decimal("3000"),
        weighted_avg_entry=Decimal("3000"),
        total_dca_legs=1,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add(pg)
    await db_session.commit()
    await db_session.refresh(pg)

    test_user.encrypted_api_keys = {"bybit": {"api_key": "test", "secret_key": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    mock_connector = AsyncMock()
    mock_connector.place_order.return_value = {"id": "mock_order_id"}
    mock_connector.cancel_order.return_value = {}
    mock_connector.get_current_price.return_value = "3100"

    with patch("app.services.position.position_manager.get_exchange_connector", return_value=mock_connector), \
         patch("app.services.position.position_closer.get_exchange_connector", return_value=mock_connector), \
         patch("app.api.positions.ExchangeConfigService") as mock_config_service:

        mock_config_service.get_connector.return_value = mock_connector
        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")

        assert response.status_code == 200
        
        await db_session.refresh(pg)
        
        assert pg.status == PositionGroupStatus.CLOSED.value

        # Assert that place_order was called to close the position
        mock_connector.place_order.assert_called_with(
            symbol="ETH/USDT",
            order_type="MARKET",
            side="SELL",
            quantity=Decimal("1"),
            price=None
        )
