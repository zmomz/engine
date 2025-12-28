import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
import uuid
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.api.dependencies.users import get_current_active_user
from app.main import app
import logging

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_force_close_position_multi_exchange_success(authorized_client, test_user, db_session):
    # 1. Create Position on 'bybit'
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="bybit",
        symbol="ETH/USDT",
        timeframe=60,
        side="short",
        status=PositionGroupStatus.ACTIVE.value,
        base_entry_price=Decimal("3000"),
        weighted_avg_entry=Decimal("3000"),
        total_dca_legs=1,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add(pg)
    await db_session.commit()
    await db_session.refresh(pg)

    # 2. Setup User Keys
    test_user.encrypted_api_keys = {"bybit": {"encrypted_data": "enc_data"}}
    db_session.add(test_user)
    await db_session.commit()

    # 3. Mocks
    mock_connector = AsyncMock()
    mock_connector.get_current_price.return_value = Decimal("2900")

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.OrderService") as mock_order_service_cls, \
         patch("app.api.positions.PositionManagerService") as mock_pm_service_cls:

        mock_config_service.get_connector.return_value = mock_connector

        mock_order_service = mock_order_service_cls.return_value
        async def mock_exec_close(group_id):
            pg.status = PositionGroupStatus.CLOSING.value
            db_session.add(pg)
            await db_session.commit()
            return pg
        mock_order_service.execute_force_close.side_effect = mock_exec_close

        mock_pm_service = mock_pm_service_cls.return_value
        mock_pm_service.handle_exit_signal = AsyncMock()

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")
        
        assert response.status_code == 200
        assert response.json()["status"] == "closing"

        mock_order_service.execute_force_close.assert_called_once_with(pg.id)
        mock_pm_service.handle_exit_signal.assert_called_once_with(pg.id, session=db_session, exit_reason="manual")



@pytest.mark.asyncio
async def test_force_close_position_connector_error(authorized_client, test_user, db_session):
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add(pg)
    await db_session.commit()
    await db_session.refresh(pg)

    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "..."}}
    db_session.add(test_user)
    await db_session.commit()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service:
        mock_config_service.get_connector.side_effect = Exception("Connection Error")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")

        assert response.status_code == 500
        # API catches and logs errors, returns generic message
        assert "An unexpected error occurred" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_position_history_unauthorized(authorized_client, test_user):
    other_user_id = uuid.uuid4()
    response = await authorized_client.get(f"/api/v1/positions/{other_user_id}/history")
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_get_position_group_not_found(authorized_client, test_user):
    fake_id = uuid.uuid4()
    response = await authorized_client.get(f"/api/v1/positions/{test_user.id}/{fake_id}")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_all_positions_unauthorized(authorized_client, test_user):
    other_user_id = uuid.uuid4()
    response = await authorized_client.get(f"/api/v1/positions/{other_user_id}")
    assert response.status_code == 403