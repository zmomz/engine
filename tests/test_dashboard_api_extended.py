import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.main import app
from app.api.dependencies.users import get_current_active_user

@pytest.mark.asyncio
async def test_get_account_summary_multi_exchange(authorized_client):
    """
    Test TVL calculation across multiple exchanges.
    """
    mock_connector_binance = AsyncMock()
    mock_connector_binance.fetch_balance.return_value = {"total": {"USDT": 1000.0, "BTC": 0.1}, "free": {"USDT": 1000.0}}
    mock_connector_binance.get_current_price.side_effect = lambda symbol: {"BTC/USDT": 40000.0}.get(symbol)
    mock_connector_binance.exchange = AsyncMock()

    mock_connector_bybit = AsyncMock()
    mock_connector_bybit.fetch_balance.return_value = {"total": {"USDT": 500.0, "ETH": 10.0}, "free": {"USDT": 500.0}}
    mock_connector_bybit.get_current_price.side_effect = lambda symbol: {"ETH/USDT": 3000.0}.get(symbol)
    mock_connector_bybit.exchange = AsyncMock()

    def side_effect_get_connector(exchange_type, **kwargs):
        if exchange_type == "binance":
            return mock_connector_binance
        elif exchange_type == "bybit":
            return mock_connector_bybit
        raise ValueError(f"Unknown exchange: {exchange_type}")

    mock_user = AsyncMock()
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "enc_binance"},
        "bybit": {"encrypted_data": "enc_bybit"}
    }
    
    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.get_exchange_connector", side_effect=side_effect_get_connector), \
             patch("app.api.dashboard.EncryptionService") as mock_encrypt_service_cls:
            
            mock_encrypt_service = mock_encrypt_service_cls.return_value
            mock_encrypt_service.decrypt_keys.return_value = ("key", "secret")

            response = await authorized_client.get("/api/v1/dashboard/account-summary")
            
            assert response.status_code == 200
            data = response.json()
            # Binance: 1000 + 0.1*40000 = 5000
            # Bybit: 500 + 10*3000 = 30500
            # Total: 35500
            assert data["tvl"] == 35500.0
            assert data["free_usdt"] == 1500.0
            
    finally:
        del app.dependency_overrides[get_current_active_user]

@pytest.mark.asyncio
async def test_get_account_summary_partial_failure(authorized_client):
    mock_connector_bybit = AsyncMock()
    mock_connector_bybit.fetch_balance.return_value = {"total": {"USDT": 500.0, "SOL": 100.0}, "free": {"USDT": 500.0}}
    mock_connector_bybit.get_current_price.side_effect = Exception("Price fetch failed")
    mock_connector_bybit.exchange = AsyncMock()

    def side_effect_get_connector(exchange_type, **kwargs):
        if exchange_type == "binance":
            raise Exception("Connection failed")
        elif exchange_type == "bybit":
            return mock_connector_bybit
        return AsyncMock()

    mock_user = AsyncMock()
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "enc_binance"},
        "bybit": {"encrypted_data": "enc_bybit"}
    }
    
    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.get_exchange_connector", side_effect=side_effect_get_connector), \
             patch("app.api.dashboard.EncryptionService") as mock_encrypt_service_cls:
            
            mock_encrypt_service = mock_encrypt_service_cls.return_value
            mock_encrypt_service.decrypt_keys.return_value = ("key", "secret")

            response = await authorized_client.get("/api/v1/dashboard/account-summary")
            
            assert response.status_code == 200
            data = response.json()
            # Binance: 0
            # Bybit: 500 (USDT) + 0 (SOL failed) = 500
            assert data["tvl"] == 500.0
            assert data["free_usdt"] == 500.0
            
    finally:
        del app.dependency_overrides[get_current_active_user]

@pytest.mark.asyncio
async def test_get_pnl_multi_exchange(authorized_client, test_user, db_session):
    # 1. Setup Positions
    p1 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_filled_quantity=Decimal("1.0"),
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    )
    p2 = PositionGroup(
        user_id=test_user.id,
        exchange="bybit",
        symbol="ETH/USDT",
        timeframe=60,
        side="short",
        total_dca_legs=1,
        base_entry_price=Decimal("3000"),
        weighted_avg_entry=Decimal("3000"),
        total_filled_quantity=Decimal("10.0"),
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    # 2. Update User Keys in DB
    # Ensure we are updating the user that matches the session used by API
    test_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "enc_bin"},
        "bybit": {"encrypted_data": "enc_by"}
    }
    db_session.add(test_user)
    await db_session.commit()

    # 3. Mock Connectors
    mock_binance = AsyncMock()
    mock_binance.get_current_price.return_value = 55000.0
    mock_binance.exchange = AsyncMock()

    mock_bybit = AsyncMock()
    mock_bybit.get_current_price.return_value = 2000.0
    mock_bybit.exchange = AsyncMock()

    def side_effect_get_connector(exchange_type, **kwargs):
        if exchange_type == "binance":
            return mock_binance
        elif exchange_type == "bybit":
            return mock_bybit
        return AsyncMock()

    async def mock_get_user():
        return test_user

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.get_exchange_connector", side_effect=side_effect_get_connector), \
             patch("app.api.dashboard.EncryptionService") as mock_encrypt_service_cls:
            
            mock_encrypt_service = mock_encrypt_service_cls.return_value
            mock_encrypt_service.decrypt_keys.return_value = ("k", "s")

            response = await authorized_client.get("/api/v1/dashboard/pnl")
            
            assert response.status_code == 200
            data = response.json()
            # Binance PnL: (55000 - 50000) * 1 = 5000
            # Bybit PnL: (3000 - 2000) * 10 = 10000
            # Total: 15000
            assert data["unrealized_pnl"] == 15000.0
    finally:
        del app.dependency_overrides[get_current_active_user]

@pytest.mark.asyncio
async def test_get_pnl_missing_keys_or_errors(authorized_client, test_user, db_session):
    p1 = PositionGroup(
        user_id=test_user.id,
        exchange="kucoin",
        symbol="SOL/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=1,
        base_entry_price=Decimal("100"),
        weighted_avg_entry=Decimal("100"),
        total_filled_quantity=Decimal("10"),
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    )
    p2 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="long",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_filled_quantity=Decimal("1"),
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    test_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "enc_bin"}
    }
    db_session.add(test_user)
    await db_session.commit()

    with (
        patch("app.api.dashboard.get_exchange_connector", side_effect=Exception("Connector failed")),
        patch("app.api.dashboard.EncryptionService")
    ):
        
        response = await authorized_client.get("/api/v1/dashboard/pnl")
        
        assert response.status_code == 200
        data = response.json()
        assert data["unrealized_pnl"] == 0.0
