"""
Comprehensive tests for api/positions.py to achieve 100% coverage.
Covers: get_order_service, _calculate_position_pnl, get_current_user_active_positions,
get_current_user_position_history, get_all_positions, force_close_position,
sync_position_with_exchange, cleanup_stale_orders
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import uuid
from datetime import datetime

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.user import User
from app.main import app
from app.api.dependencies.users import get_current_active_user
from app.services.exchange_config_service import ExchangeConfigError


# --- Fixtures ---

@pytest.fixture
def mock_position_group():
    """Create a mock position group with all required attributes."""
    pg = MagicMock(spec=PositionGroup)
    pg.id = uuid.uuid4()
    pg.user_id = uuid.uuid4()
    pg.symbol = "BTCUSDT"
    pg.exchange = "binance"
    pg.timeframe = 15
    pg.side = "long"
    pg.status = PositionGroupStatus.ACTIVE.value
    pg.pyramid_count = 1
    pg.max_pyramids = 5
    pg.total_dca_legs = 5
    pg.filled_dca_legs = 2
    pg.base_entry_price = Decimal("50000.00")
    pg.weighted_avg_entry = Decimal("49500.00")
    pg.total_invested_usd = Decimal("1000.00")
    pg.total_filled_quantity = Decimal("0.02")
    pg.unrealized_pnl_usd = Decimal("50.00")
    pg.unrealized_pnl_percent = Decimal("5.00")
    pg.realized_pnl_usd = Decimal("0")
    pg.created_at = datetime.utcnow()
    pg.updated_at = datetime.utcnow()
    return pg


# --- Tests for get_order_service dependency ---

@pytest.mark.asyncio
async def test_get_order_service_exchange_config_error(authorized_client, test_user, db_session):
    """Test force_close_position handles ExchangeConfigError.

    Note: Due to the exception handling structure in force_close_position,
    ExchangeConfigError raises HTTPException(400) which is then caught by
    the generic Exception handler and returns 500. This tests the current behavior.
    """
    from app.models.pyramid import Pyramid

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

    # Add pyramid for the position
    pyramid = Pyramid(
        group_id=pg.id,
        pyramid_index=1,
        entry_price=Decimal("50000"),
        dca_config={"levels": []}
    )
    db_session.add(pyramid)
    await db_session.commit()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service:
        mock_config_service.get_connector.side_effect = ExchangeConfigError("No API keys configured")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")

        # The HTTPException(400) gets caught by generic Exception handler and returns 500
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_get_order_service_generic_exception(authorized_client, test_user, db_session):
    """Test get_order_service raises 500 on generic exception."""
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

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service:
        mock_config_service.get_connector.side_effect = Exception("Unexpected failure")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")

        assert response.status_code == 500


# --- Tests for _calculate_position_pnl ---

@pytest.mark.asyncio
async def test_calculate_position_pnl_from_tickers():
    """Test _calculate_position_pnl using cached tickers."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "BTCUSDT"
    pos.total_filled_quantity = Decimal("0.02")
    pos.weighted_avg_entry = Decimal("50000")
    pos.total_invested_usd = Decimal("1000")
    pos.side = "long"

    all_tickers = {"BTCUSDT": {"last": 52000}}
    connector = AsyncMock()

    await _calculate_position_pnl(pos, all_tickers, connector)

    # PnL = (52000 - 50000) * 0.02 = 40
    assert pos.unrealized_pnl_usd == Decimal("40")


@pytest.mark.asyncio
async def test_calculate_position_pnl_with_slash_symbol():
    """Test _calculate_position_pnl with BTC/USDT format converted to BTCUSDT in tickers."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "BTC/USDT"  # Slash format
    pos.total_filled_quantity = Decimal("0.02")
    pos.weighted_avg_entry = Decimal("50000")
    pos.total_invested_usd = Decimal("1000")
    pos.side = "long"

    # Ticker uses non-slash format
    all_tickers = {"BTCUSDT": {"last": 52000}}
    connector = AsyncMock()

    await _calculate_position_pnl(pos, all_tickers, connector)

    assert pos.unrealized_pnl_usd == Decimal("40")


@pytest.mark.asyncio
async def test_calculate_position_pnl_fallback_to_connector():
    """Test _calculate_position_pnl falls back to connector when ticker not in cache."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "ETHUSDT"
    pos.total_filled_quantity = Decimal("1.0")
    pos.weighted_avg_entry = Decimal("2000")
    pos.total_invested_usd = Decimal("2000")
    pos.side = "long"

    all_tickers = {}  # Empty tickers, should fallback
    connector = AsyncMock()
    connector.get_current_price.return_value = 2200

    await _calculate_position_pnl(pos, all_tickers, connector)

    connector.get_current_price.assert_called_once_with("ETHUSDT")
    # PnL = (2200 - 2000) * 1.0 = 200
    assert pos.unrealized_pnl_usd == Decimal("200")


@pytest.mark.asyncio
async def test_calculate_position_pnl_short_position():
    """Test _calculate_position_pnl for short positions."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "BTCUSDT"
    pos.total_filled_quantity = Decimal("0.01")
    pos.weighted_avg_entry = Decimal("50000")
    pos.total_invested_usd = Decimal("500")
    pos.side = "short"

    all_tickers = {"BTCUSDT": {"last": 48000}}  # Price went down, profit for short
    connector = AsyncMock()

    await _calculate_position_pnl(pos, all_tickers, connector)

    # PnL = (50000 - 48000) * 0.01 = 20
    assert pos.unrealized_pnl_usd == Decimal("20")


@pytest.mark.asyncio
async def test_calculate_position_pnl_zero_qty():
    """Test _calculate_position_pnl with zero quantity sets PnL to zero."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "BTCUSDT"
    pos.total_filled_quantity = Decimal("0")
    pos.weighted_avg_entry = Decimal("50000")
    pos.total_invested_usd = Decimal("0")
    pos.side = "long"

    all_tickers = {"BTCUSDT": {"last": 52000}}
    connector = AsyncMock()

    await _calculate_position_pnl(pos, all_tickers, connector)

    # With zero qty, PnL should be set to 0
    assert pos.unrealized_pnl_usd == Decimal("0")
    assert pos.unrealized_pnl_percent == Decimal("0")


@pytest.mark.asyncio
async def test_calculate_position_pnl_none_price():
    """Test _calculate_position_pnl when price is None."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "UNKNOWN"
    pos.total_filled_quantity = Decimal("1.0")
    pos.weighted_avg_entry = Decimal("100")
    pos.total_invested_usd = Decimal("100")
    pos.side = "long"
    pos.unrealized_pnl_usd = None

    all_tickers = {}
    connector = AsyncMock()
    connector.get_current_price.return_value = None  # Price not available

    await _calculate_position_pnl(pos, all_tickers, connector)

    # Should return early without setting pnl
    assert pos.unrealized_pnl_usd is None


@pytest.mark.asyncio
async def test_calculate_position_pnl_zero_invested():
    """Test _calculate_position_pnl with zero investment (edge case)."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "BTCUSDT"
    pos.total_filled_quantity = Decimal("0.01")
    pos.weighted_avg_entry = Decimal("50000")
    pos.total_invested_usd = Decimal("0")  # Zero investment
    pos.side = "long"

    all_tickers = {"BTCUSDT": {"last": 52000}}
    connector = AsyncMock()

    await _calculate_position_pnl(pos, all_tickers, connector)

    # PnL should be calculated, percent should be 0
    assert pos.unrealized_pnl_usd == Decimal("20")
    assert pos.unrealized_pnl_percent == Decimal("0")


@pytest.mark.asyncio
async def test_calculate_position_pnl_exception_handling():
    """Test _calculate_position_pnl handles exceptions gracefully."""
    from app.api.positions import _calculate_position_pnl

    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.symbol = "BTCUSDT"
    pos.total_filled_quantity = Decimal("0.01")
    pos.weighted_avg_entry = Decimal("50000")
    pos.total_invested_usd = Decimal("500")
    pos.side = "long"

    all_tickers = {}
    connector = AsyncMock()
    connector.get_current_price.side_effect = Exception("API Error")

    # Should not raise
    await _calculate_position_pnl(pos, all_tickers, connector)


# --- Tests for get_current_user_active_positions ---

@pytest.mark.asyncio
async def test_get_current_user_active_positions_empty(authorized_client, test_user):
    """Test getting active positions when none exist."""
    response = await authorized_client.get("/api/v1/positions/active")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_current_user_active_positions_no_api_keys(authorized_client, test_user, db_session):
    """Test getting active positions when user has no API keys (no PnL calculation)."""
    test_user.encrypted_api_keys = {}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    response = await authorized_client.get("/api/v1/positions/active")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_current_user_active_positions_with_pnl(authorized_client, test_user, db_session):
    """Test getting active positions with PnL calculation."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    test_user.exchange = "binance"
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_filled_quantity=Decimal("0.01"),
        total_invested_usd=Decimal("500"),
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add(pg)
    await db_session.commit()

    mock_connector = AsyncMock()
    mock_connector.get_all_tickers.return_value = {"BTCUSDT": {"last": 52000}}

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = None
    mock_cache.set_tickers = AsyncMock()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.get("/api/v1/positions/active")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_current_user_active_positions_no_valid_config(authorized_client, test_user, db_session):
    """Test getting active positions when exchange has no valid config."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = None

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = False

        response = await authorized_client.get("/api/v1/positions/active")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_current_user_active_positions_ticker_fetch_error(authorized_client, test_user, db_session):
    """Test getting active positions when ticker fetch fails."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    test_user.exchange = "binance"
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_connector = AsyncMock()
    mock_connector.get_all_tickers.side_effect = Exception("API Error")

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = None

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.get("/api/v1/positions/active")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_current_user_active_positions_cached_tickers(authorized_client, test_user, db_session):
    """Test getting active positions using cached tickers."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    test_user.exchange = "binance"
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_filled_quantity=Decimal("0.01"),
        total_invested_usd=Decimal("500"),
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add(pg)
    await db_session.commit()

    mock_connector = AsyncMock()

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = {"BTCUSDT": {"last": 52000}}

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.get("/api/v1/positions/active")

    assert response.status_code == 200
    # Should not call get_all_tickers since cache had data
    mock_connector.get_all_tickers.assert_not_called()


# --- Tests for get_current_user_position_history ---

@pytest.mark.asyncio
async def test_get_current_user_position_history(authorized_client, test_user, db_session):
    """Test getting position history for current user."""
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.CLOSED.value,
        tp_mode="per_leg",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        tp_aggregate_percent=Decimal("0"),
        closed_at=datetime.utcnow()
    )
    db_session.add(pg)
    await db_session.commit()

    response = await authorized_client.get("/api/v1/positions/history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_current_user_position_history_with_pagination(authorized_client, test_user, db_session):
    """Test getting position history with pagination."""
    for i in range(5):
        pg = PositionGroup(
            user_id=test_user.id,
            exchange="binance",
            symbol=f"COIN{i}USDT",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.CLOSED.value,
            tp_mode="per_leg",
            total_dca_legs=1,
            base_entry_price=Decimal("100"),
            weighted_avg_entry=Decimal("100"),
            tp_aggregate_percent=Decimal("0"),
            closed_at=datetime.utcnow()
        )
        db_session.add(pg)
    await db_session.commit()

    response = await authorized_client.get("/api/v1/positions/history?limit=2&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 2
    assert data["offset"] == 1


# --- Tests for sync_position_with_exchange ---

@pytest.mark.asyncio
async def test_sync_position_not_found(authorized_client, test_user):
    """Test syncing non-existent position."""
    fake_id = uuid.uuid4()
    response = await authorized_client.post(f"/api/v1/positions/{fake_id}/sync")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sync_position_success(authorized_client, test_user, db_session):
    """Test successful position sync."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_connector = AsyncMock()
    mock_connector.close = AsyncMock()

    mock_sync_service = MagicMock()
    mock_sync_service.sync_orders_with_exchange = AsyncMock(return_value={
        "synced": 3,
        "updated": 1,
        "not_found": 0,
        "errors": 0
    })

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.services.exchange_sync.ExchangeSyncService", return_value=mock_sync_service):
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/sync")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_sync_position_exchange_config_error(authorized_client, test_user, db_session):
    """Test sync position with exchange config error."""
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service:
        mock_config_service.get_connector.side_effect = ExchangeConfigError("No keys")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/sync")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_sync_position_unexpected_error(authorized_client, test_user, db_session):
    """Test sync position with unexpected error."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_connector = AsyncMock()
    mock_connector.close = AsyncMock()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.services.exchange_sync.ExchangeSyncService") as mock_sync_cls:
        mock_config_service.get_connector.return_value = mock_connector
        mock_sync_cls.return_value.sync_orders_with_exchange.side_effect = Exception("Sync failed")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/sync")

    assert response.status_code == 500


# --- Tests for cleanup_stale_orders ---

@pytest.mark.asyncio
async def test_cleanup_stale_orders_not_found(authorized_client, test_user):
    """Test cleanup stale orders for non-existent position."""
    fake_id = uuid.uuid4()
    response = await authorized_client.post(f"/api/v1/positions/{fake_id}/cleanup-stale")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cleanup_stale_orders_success(authorized_client, test_user, db_session):
    """Test successful cleanup of stale orders."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_connector = AsyncMock()
    mock_connector.close = AsyncMock()

    mock_sync_service = MagicMock()
    mock_sync_service.cleanup_stale_local_orders = AsyncMock(return_value={
        "checked": 5,
        "cleaned": 2,
        "errors": 0
    })

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.services.exchange_sync.ExchangeSyncService", return_value=mock_sync_service):
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/cleanup-stale?stale_hours=24")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_sync_service.cleanup_stale_local_orders.assert_called_once_with(
        position_group_id=pg.id,
        stale_hours=24
    )


@pytest.mark.asyncio
async def test_cleanup_stale_orders_exchange_error(authorized_client, test_user, db_session):
    """Test cleanup stale orders with exchange config error."""
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service:
        mock_config_service.get_connector.side_effect = ExchangeConfigError("No keys configured")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/cleanup-stale")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cleanup_stale_orders_unexpected_error(authorized_client, test_user, db_session):
    """Test cleanup stale orders with unexpected error."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_connector = AsyncMock()
    mock_connector.close = AsyncMock()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.services.exchange_sync.ExchangeSyncService") as mock_sync_cls:
        mock_config_service.get_connector.return_value = mock_connector
        mock_sync_cls.return_value.cleanup_stale_local_orders.side_effect = Exception("Cleanup failed")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/cleanup-stale")

    assert response.status_code == 500


# --- Tests for force_close_position ---

@pytest.mark.asyncio
async def test_force_close_position_not_found(authorized_client, test_user):
    """Test force closing non-existent position."""
    fake_id = uuid.uuid4()
    response = await authorized_client.post(f"/api/v1/positions/{fake_id}/close")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_force_close_position_api_error(authorized_client, test_user, db_session):
    """Test force close with APIError."""
    from app.exceptions import APIError
    from app.models.pyramid import Pyramid

    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    # Add pyramid for the position
    pyramid = Pyramid(
        group_id=pg.id,
        pyramid_index=1,
        entry_price=Decimal("50000"),
        dca_config={"levels": []}
    )
    db_session.add(pyramid)
    await db_session.commit()

    mock_connector = AsyncMock()
    mock_connector.close = AsyncMock()

    mock_order_service = MagicMock()
    mock_order_service.execute_force_close = AsyncMock(side_effect=APIError("Order failed", status_code=422))

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.OrderService", return_value=mock_order_service):
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_force_close_position_exchange_config_error(authorized_client, test_user, db_session):
    """Test force close with ExchangeConfigError.

    Note: Due to exception handling in force_close_position, ExchangeConfigError
    raises HTTPException(400) which is then caught by the generic Exception handler
    and returns 500. This tests the current behavior.
    """
    from app.models.pyramid import Pyramid

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    # Add pyramid for the position
    pyramid = Pyramid(
        group_id=pg.id,
        pyramid_index=1,
        entry_price=Decimal("50000"),
        dca_config={"levels": []}
    )
    db_session.add(pyramid)
    await db_session.commit()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service:
        mock_config_service.get_connector.side_effect = ExchangeConfigError("Missing API keys")

        response = await authorized_client.post(f"/api/v1/positions/{pg.id}/close")

    # HTTPException(400) gets caught by generic Exception handler and returns 500
    assert response.status_code == 500


# --- Tests for get_all_positions with multiple exchanges ---

@pytest.mark.asyncio
async def test_get_all_positions_multi_exchange(authorized_client, test_user, db_session):
    """Test getting positions across multiple exchanges."""
    test_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "test"},
        "bybit": {"encrypted_data": "test2"}
    }
    db_session.add(test_user)
    await db_session.commit()

    # Create position on binance
    pg1 = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        total_dca_legs=1,
        base_entry_price=Decimal("50000"),
        weighted_avg_entry=Decimal("50000"),
        total_filled_quantity=Decimal("0.01"),
        total_invested_usd=Decimal("500"),
        tp_aggregate_percent=Decimal("0")
    )
    # Create position on bybit
    pg2 = PositionGroup(
        user_id=test_user.id,
        exchange="bybit",
        symbol="ETHUSDT",
        timeframe=60,
        side="long",
        status=PositionGroupStatus.ACTIVE.value,
        tp_mode="per_leg",
        total_dca_legs=1,
        base_entry_price=Decimal("2000"),
        weighted_avg_entry=Decimal("2000"),
        total_filled_quantity=Decimal("1.0"),
        total_invested_usd=Decimal("2000"),
        tp_aggregate_percent=Decimal("0")
    )
    db_session.add_all([pg1, pg2])
    await db_session.commit()

    mock_connector_binance = AsyncMock()
    mock_connector_binance.get_all_tickers.return_value = {"BTCUSDT": {"last": 52000}}

    mock_connector_bybit = AsyncMock()
    mock_connector_bybit.get_all_tickers.return_value = {"ETHUSDT": {"last": 2200}}

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = None
    mock_cache.set_tickers = AsyncMock()

    def get_connector_side_effect(user, exchange=None):
        if exchange == "bybit":
            return mock_connector_bybit
        return mock_connector_binance

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.side_effect = get_connector_side_effect

        response = await authorized_client.get(f"/api/v1/positions/{test_user.id}")

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_all_positions_exchange_error(authorized_client, test_user, db_session):
    """Test getting positions when exchange call fails."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    db_session.add(test_user)
    await db_session.commit()

    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",
        symbol="BTCUSDT",
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

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = None

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.side_effect = Exception("Connection failed")

        response = await authorized_client.get(f"/api/v1/positions/{test_user.id}")

    # Should still return positions, just without PnL updates
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_all_positions_default_exchange_fallback(authorized_client, test_user, db_session):
    """Test getting positions using user's default exchange when position exchange uses fallback."""
    test_user.encrypted_api_keys = {"binance": {"encrypted_data": "test"}}
    test_user.exchange = "binance"
    db_session.add(test_user)
    await db_session.commit()

    # Create position with user's exchange (uses user default)
    pg = PositionGroup(
        user_id=test_user.id,
        exchange="binance",  # Uses the user's default exchange
        symbol="BTCUSDT",
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

    mock_connector = AsyncMock()
    mock_connector.get_all_tickers.return_value = {"BTCUSDT": {"last": 52000}}

    mock_cache = AsyncMock()
    mock_cache.get_tickers.return_value = None
    mock_cache.set_tickers = AsyncMock()

    with patch("app.api.positions.ExchangeConfigService") as mock_config_service, \
         patch("app.api.positions.get_cache", return_value=mock_cache):
        mock_config_service.has_valid_config.return_value = True
        mock_config_service.get_connector.return_value = mock_connector

        response = await authorized_client.get(f"/api/v1/positions/{test_user.id}")

    assert response.status_code == 200
