import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from app.models.position_group import PositionGroup, PositionGroupStatus

# Test TVL
@pytest.mark.asyncio
async def test_get_tvl(authorized_client):
    # Mock connector
    mock_connector = AsyncMock()
    # CCXT structure: {'total': {'USDT': 5000.50}, ...}
    mock_connector.fetch_balance.return_value = {"total": {"USDT": 5000.50}}
    mock_connector.exchange = AsyncMock() # For close()

    with patch("app.api.dashboard.get_exchange_connector", return_value=mock_connector) as mock_get_conn, \
         patch("app.api.dashboard.EncryptionService") as mock_encrypt_service_cls:
        
        # Mock the instance returned by EncryptionService()
        mock_encrypt_service = mock_encrypt_service_cls.return_value
        mock_encrypt_service.decrypt_keys.return_value = ("dummy_api", "dummy_secret")

        response = await authorized_client.get("/api/v1/dashboard/tvl")
        
        assert response.status_code == 200

        assert response.json() == {"tvl": 5000.50}
        
        # Verify cleanup
        if hasattr(mock_connector, 'exchange') and hasattr(mock_connector.exchange, 'close'):
             mock_connector.exchange.close.assert_called_once()


# Test PnL
@pytest.mark.asyncio
async def test_get_pnl(authorized_client, test_user, db_session):
    # Seed data
    p1 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=3,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        tp_mode="aggregate",
        status=PositionGroupStatus.CLOSED.value,
        realized_pnl_usd=Decimal("100.00"),
        unrealized_pnl_usd=Decimal("0.00")
    )
    p2 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="ETH/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=3,
        base_entry_price=Decimal("3000"),
        weighted_avg_entry=Decimal("3000"),
        tp_mode="aggregate",
        status=PositionGroupStatus.ACTIVE.value,
        realized_pnl_usd=Decimal("10.00"),
        unrealized_pnl_usd=Decimal("50.50")
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    response = await authorized_client.get("/api/v1/dashboard/pnl")
    
    assert response.status_code == 200
    # 100 + 10 + 50.50 = 160.50
    assert response.json() == {"pnl": 160.50}

# Test Active Groups Count
@pytest.mark.asyncio
async def test_get_active_groups_count(authorized_client, test_user, db_session):
    # Seed data
    p1 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=3,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        tp_mode="aggregate",
        status=PositionGroupStatus.ACTIVE.value, # Active
    )
    p2 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="ETH/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=3,
        base_entry_price=Decimal("3000"),
        weighted_avg_entry=Decimal("3000"),
        tp_mode="aggregate",
        status=PositionGroupStatus.CLOSED.value, # Closed
    )
    p3 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="SOL/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=3,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        tp_mode="aggregate",
        status=PositionGroupStatus.LIVE.value, # Active
    )
    db_session.add_all([p1, p2, p3])
    await db_session.commit()

    response = await authorized_client.get("/api/v1/dashboard/active-groups-count")
    
    assert response.status_code == 200
    assert response.json() == {"count": 2}
