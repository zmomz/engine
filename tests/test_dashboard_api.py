import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
from app.models.position_group import PositionGroup, PositionGroupStatus
from app.main import app
from app.api.dependencies.users import get_current_active_user

# Test TVL
@pytest.mark.asyncio
async def test_get_account_summary(authorized_client):
    # Mock connector
    mock_connector = AsyncMock()
    mock_connector.fetch_balance.return_value = {"USDT": Decimal("5000.50"), "BTC": Decimal("0.1")}
    mock_connector.get_all_tickers.return_value = {"BTC/USDT": {"last": 40000.0}}
    mock_connector.get_current_price.side_effect = lambda symbol: {
        "BTC/USDT": 40000.0,
        "BTCUSDT": 40000.0,
    }.get(symbol)

    mock_user = MagicMock()
    mock_user.id = "test-user-id-summary"
    mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "mock_encrypted_data"}}
    mock_user.exchange = "binance"

    async def mock_get_user():
        return mock_user

    # Mock cache to return None (no cached data)
    mock_cache = AsyncMock()
    mock_cache.get_dashboard.return_value = None
    mock_cache.get_balance.return_value = None
    mock_cache.get_tickers.return_value = None
    mock_cache.set_dashboard.return_value = True
    mock_cache.set_balance.return_value = True
    mock_cache.set_tickers.return_value = True

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service, \
             patch("app.api.dashboard.get_cache", return_value=mock_cache):
            # Mock the get_all_configured_exchanges to return binance
            mock_config_service.get_all_configured_exchanges.return_value = {
                "binance": {"encrypted_data": "mock_encrypted_data"}
            }
            # Mock get_connector to return our mock connector
            mock_config_service.get_connector.return_value = mock_connector

            response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            # TVL: 5000.50 USDT + 0.1 BTC * 40000 = 5000.50 + 4000 = 9000.50
            assert data["tvl"] == 9000.50
            assert data["free_usdt"] == 5000.50
    finally:
        del app.dependency_overrides[get_current_active_user]



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
        total_filled_quantity=Decimal("0.1"),  # Needed for calculation
        tp_mode="aggregate",
        status=PositionGroupStatus.ACTIVE.value,
        realized_pnl_usd=Decimal("10.00"),
        unrealized_pnl_usd=Decimal("50.50")  # This is ignored now by the API logic
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    # Mock connector
    mock_connector = AsyncMock()
    mock_connector.get_all_tickers.return_value = {"ETH/USDT": {"last": 3505.0}}
    mock_connector.get_current_price.side_effect = lambda symbol: {
        "ETH/USDT": 3505.0,  # (3505 - 3000) * 0.1 = 50.5
    }.get(symbol)

    with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service:
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.get("/api/v1/dashboard/pnl")

        assert response.status_code == 200
        # 100 + 10 + 50.50 = 160.50
        assert response.json() == {"pnl": 160.50, "realized_pnl": 110.00, "unrealized_pnl": 50.50}

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


# Test Stats
@pytest.mark.asyncio
async def test_get_stats(authorized_client, test_user, db_session):
    """Test the /stats endpoint returns correct win/loss statistics."""
    # Seed data with closed positions
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
        realized_pnl_usd=Decimal("100.00"),  # Winner
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
        status=PositionGroupStatus.CLOSED.value,
        realized_pnl_usd=Decimal("-50.00"),  # Loser
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
        status=PositionGroupStatus.CLOSED.value,
        realized_pnl_usd=Decimal("25.00"),  # Winner
    )
    db_session.add_all([p1, p2, p3])
    await db_session.commit()

    response = await authorized_client.get("/api/v1/dashboard/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_trades"] == 3
    assert data["total_winning_trades"] == 2
    assert data["total_losing_trades"] == 1
    # Win rate should be approximately 66.67%
    assert abs(data["win_rate"] - 66.67) < 1


@pytest.mark.asyncio
async def test_get_stats_no_trades(authorized_client, test_user, db_session):
    """Test the /stats endpoint with no closed trades."""
    response = await authorized_client.get("/api/v1/dashboard/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_trades"] == 0
    assert data["total_winning_trades"] == 0
    assert data["total_losing_trades"] == 0
    assert data["win_rate"] == 0.0


@pytest.mark.asyncio
async def test_get_account_summary_no_api_keys(authorized_client):
    """Test account summary returns zeros when user has no API keys."""
    mock_user = AsyncMock()
    mock_user.encrypted_api_keys = None

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        response = await authorized_client.get("/api/v1/dashboard/account-summary")

        assert response.status_code == 200
        assert response.json() == {"tvl": 0.0, "free_usdt": 0.0}
    finally:
        del app.dependency_overrides[get_current_active_user]


@pytest.mark.asyncio
async def test_get_account_summary_empty_api_keys(authorized_client):
    """Test account summary returns zeros when user has empty API keys dict."""
    mock_user = AsyncMock()
    mock_user.encrypted_api_keys = {}

    async def mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        response = await authorized_client.get("/api/v1/dashboard/account-summary")

        assert response.status_code == 200
        assert response.json() == {"tvl": 0.0, "free_usdt": 0.0}
    finally:
        del app.dependency_overrides[get_current_active_user]


@pytest.mark.asyncio
async def test_get_account_summary_legacy_key_format(authorized_client):
    """Test account summary handles legacy string format for API keys."""
    mock_connector = AsyncMock()
    mock_connector.fetch_balance.return_value = {"USDT": Decimal("1000.0")}
    mock_connector.get_all_tickers.return_value = {}
    mock_connector.get_current_price = AsyncMock(return_value=0)

    mock_user = MagicMock()
    mock_user.id = "test-user-id-legacy"
    # Legacy format: string directly instead of dict
    mock_user.encrypted_api_keys = {"binance": "legacy_encrypted_string"}
    mock_user.exchange = "binance"

    async def mock_get_user():
        return mock_user

    # Mock cache to return None (no cached data)
    mock_cache = AsyncMock()
    mock_cache.get_dashboard.return_value = None
    mock_cache.get_balance.return_value = None
    mock_cache.get_tickers.return_value = None
    mock_cache.set_dashboard.return_value = True
    mock_cache.set_balance.return_value = True
    mock_cache.set_tickers.return_value = True

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service, \
             patch("app.api.dashboard.get_cache", return_value=mock_cache):
            mock_config_service.get_all_configured_exchanges.return_value = {
                "binance": {"encrypted_data": "legacy_encrypted_string"}
            }
            mock_config_service.get_connector.return_value = mock_connector

            response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            assert data["tvl"] == 1000.0
    finally:
        del app.dependency_overrides[get_current_active_user]


@pytest.mark.asyncio
async def test_get_account_summary_exchange_error(authorized_client):
    """Test account summary handles exchange errors gracefully."""
    mock_connector = AsyncMock()
    mock_connector.fetch_balance.side_effect = Exception("Exchange API error")

    mock_user = MagicMock()
    mock_user.id = "test-user-id-error"
    mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "mock_data"}}
    mock_user.exchange = "binance"

    async def mock_get_user():
        return mock_user

    # Mock cache to return None (no cached data)
    mock_cache = AsyncMock()
    mock_cache.get_dashboard.return_value = None
    mock_cache.get_balance.return_value = None
    mock_cache.get_tickers.return_value = None
    mock_cache.set_dashboard.return_value = True
    mock_cache.set_balance.return_value = True
    mock_cache.set_tickers.return_value = True

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service, \
             patch("app.api.dashboard.get_cache", return_value=mock_cache):
            mock_config_service.get_all_configured_exchanges.return_value = {
                "binance": {"encrypted_data": "mock_data"}
            }
            mock_config_service.get_connector.return_value = mock_connector

            response = await authorized_client.get("/api/v1/dashboard/account-summary")

            # Should still return 200 with zeros, not fail
            assert response.status_code == 200
            data = response.json()
            assert data["tvl"] == 0.0
    finally:
        del app.dependency_overrides[get_current_active_user]


@pytest.mark.asyncio
async def test_get_pnl_no_active_positions(authorized_client, test_user, db_session):
    """Test PnL endpoint with only closed positions (no unrealized)."""
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
        realized_pnl_usd=Decimal("150.00"),
    )
    db_session.add(p1)
    await db_session.commit()

    response = await authorized_client.get("/api/v1/dashboard/pnl")

    assert response.status_code == 200
    data = response.json()
    assert data["realized_pnl"] == 150.0
    assert data["unrealized_pnl"] == 0.0
    assert data["pnl"] == 150.0


@pytest.mark.asyncio
async def test_get_pnl_short_position(authorized_client, test_user, db_session):
    """Test PnL calculation for short positions."""
    # Short position: profit when price drops
    p1 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=60,
        side="short",  # Short position
        total_dca_legs=3,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_filled_quantity=Decimal("0.1"),
        tp_mode="aggregate",
        status=PositionGroupStatus.ACTIVE.value,
        realized_pnl_usd=Decimal("0.00"),
    )
    db_session.add(p1)
    await db_session.commit()

    mock_connector = AsyncMock()
    # Price dropped to 48000 -> profit for short
    mock_connector.get_current_price.return_value = 48000.0
    mock_connector.get_all_tickers.return_value = {"BTC/USDT": {"last": 48000.0}}

    with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service:
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.get("/api/v1/dashboard/pnl")

        assert response.status_code == 200
        data = response.json()
        # Short PnL: (entry - current) * qty = (50000 - 48000) * 0.1 = 200
        assert data["unrealized_pnl"] == 200.0


@pytest.mark.asyncio
async def test_get_account_summary_with_get_all_tickers(authorized_client):
    """Test account summary uses get_all_tickers for efficiency."""
    mock_connector = AsyncMock()
    mock_connector.fetch_balance.return_value = {"USDT": Decimal("1000.0"), "BTC": Decimal("0.5"), "ETH": Decimal("2.0")}
    mock_connector.get_all_tickers.return_value = {
        "BTC/USDT": {"last": 40000.0},
        "ETH/USDT": {"last": 2000.0}
    }
    mock_connector.get_current_price = AsyncMock()  # Should not be called if tickers work

    mock_user = MagicMock()
    mock_user.id = "test-user-id-tickers"
    mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "mock_data"}}
    mock_user.exchange = "binance"

    async def mock_get_user():
        return mock_user

    # Mock cache to return None (no cached data)
    mock_cache = AsyncMock()
    mock_cache.get_dashboard.return_value = None
    mock_cache.get_balance.return_value = None
    mock_cache.get_tickers.return_value = None
    mock_cache.set_dashboard.return_value = True
    mock_cache.set_balance.return_value = True
    mock_cache.set_tickers.return_value = True

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service, \
             patch("app.api.dashboard.get_cache", return_value=mock_cache):
            mock_config_service.get_all_configured_exchanges.return_value = {
                "binance": {"encrypted_data": "mock_data"}
            }
            mock_config_service.get_connector.return_value = mock_connector

            response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            # TVL: 1000 USDT + 0.5 BTC * 40000 + 2 ETH * 2000 = 1000 + 20000 + 4000 = 25000
            assert data["tvl"] == 25000.0
    finally:
        del app.dependency_overrides[get_current_active_user]


@pytest.mark.asyncio
async def test_get_account_summary_skips_dust_balances(authorized_client):
    """Test that account summary skips dust balances below threshold."""
    mock_connector = AsyncMock()
    mock_connector.fetch_balance.return_value = {
        "USDT": Decimal("1000.0"),
        "DOGE": Decimal("0.001")  # Very small amount
    }
    mock_connector.get_all_tickers.return_value = {
        "DOGE/USDT": {"last": 0.08}  # 0.001 * 0.08 = 0.00008 USD (below $0.10 threshold)
    }

    mock_user = MagicMock()
    mock_user.id = "test-user-id-dust"
    mock_user.encrypted_api_keys = {"binance": {"encrypted_data": "mock_data"}}
    mock_user.exchange = "binance"

    async def mock_get_user():
        return mock_user

    # Mock cache to return None (no cached data)
    mock_cache = AsyncMock()
    mock_cache.get_dashboard.return_value = None
    mock_cache.get_balance.return_value = None
    mock_cache.get_tickers.return_value = None
    mock_cache.set_dashboard.return_value = True
    mock_cache.set_balance.return_value = True
    mock_cache.set_tickers.return_value = True

    app.dependency_overrides[get_current_active_user] = mock_get_user

    try:
        with patch("app.api.dashboard.ExchangeConfigService") as mock_config_service, \
             patch("app.api.dashboard.get_cache", return_value=mock_cache):
            mock_config_service.get_all_configured_exchanges.return_value = {
                "binance": {"encrypted_data": "mock_data"}
            }
            mock_config_service.get_connector.return_value = mock_connector

            response = await authorized_client.get("/api/v1/dashboard/account-summary")

            assert response.status_code == 200
            data = response.json()
            # Should only include USDT, not the dust DOGE balance
            assert data["tvl"] == 1000.0
    finally:
        del app.dependency_overrides[get_current_active_user]
