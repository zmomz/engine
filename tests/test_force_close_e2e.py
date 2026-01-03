
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
import uuid
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
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

    # Create a Pyramid first (required for DCAOrder)
    pyramid = Pyramid(
        group_id=pg.id,
        pyramid_index=0,
        entry_price=Decimal("3000"),
        status=PyramidStatus.FILLED.value,
        dca_config={"levels": []}
    )
    db_session.add(pyramid)
    await db_session.commit()
    await db_session.refresh(pyramid)

    # Create a filled DCA order so the position has a quantity to close
    filled_order = DCAOrder(
        group_id=pg.id,
        pyramid_id=pyramid.id,
        leg_index=0,
        symbol="ETH/USDT",
        side="buy",
        order_type="market",
        price=Decimal("3000"),
        quantity=Decimal("1"),
        filled_quantity=Decimal("1"),
        status=OrderStatus.FILLED.value,
        gap_percent=Decimal("0"),
        weight_percent=Decimal("100"),
        tp_percent=Decimal("1"),
        tp_price=Decimal("3030")
    )
    db_session.add(filled_order)
    await db_session.commit()

    test_user.encrypted_api_keys = {"bybit": {"api_key": "test", "secret_key": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    mock_connector = AsyncMock()
    mock_connector.place_order.return_value = {"id": "mock_order_id"}
    mock_connector.cancel_order.return_value = {}
    mock_connector.get_current_price.return_value = "3100"
    mock_connector.get_trading_fee_rate.return_value = "0.001"
    mock_connector.close = AsyncMock()

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
