import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.db.database import get_db_session
from app.models.queued_signal import QueuedSignal
from app.models.user import User
from app.repositories.user import UserRepository # Import UserRepository
from app.db.types import GUID
import uuid
import json
import hmac
import hashlib

# Mock the get_db_session dependency for testing
@pytest.fixture
async def test_db_session():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute.return_value = result_mock
    yield session

@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejection(test_db_session, mocker):
    """
    Test that webhooks with invalid signatures are rejected.
    """
    user_id = uuid.uuid4()
    
    class MockUser:
        def __init__(self, id, webhook_secret):
            self.id = id
            self.username = "test_user"
            self.webhook_secret = webhook_secret
            self.encrypted_api_keys = {"encrypted_data": "dummy"}
            self.exchange = "binance"
            self.risk_config = {}
            self.dca_grid_config = {}

    mock_user_instance = MockUser(id=user_id, webhook_secret="valid_secret")

    # Mock UserRepository.get_by_id to return our mock_user_instance
    mocker.patch.object(UserRepository, "get_by_id", AsyncMock(return_value=mock_user_instance))

    app.dependency_overrides[get_db_session] = lambda: test_db_session
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Simulate an invalid signature by sending a wrong secret
        payload = {
            "tv": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "timeframe": 15,
                "entry_price": 50000,
                "action": "long",
                "market_position": "long",
                "market_position_size": 0.0,
                "prev_market_position": "flat",
                "prev_market_position_size": 0.0,
                "close_price": 50000,
                "order_size": 0.1
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "base",
                "precision_mode": "auto"
            },
            "strategy_info": {
                "trade_id": "test_trade",
                "alert_name": "test_alert",
                "alert_message": "test_message"
            },
            "risk": {
                "max_slippage_percent": 0.5
            },
            "secret": "some_secret", # This does not match "valid_secret"
            "source": "tradingview",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": str(user_id)
        }
        # Use the correct URL with user_id
        response = await ac.post(f"/api/v1/webhooks/{user_id}/tradingview", json=payload)

        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid secret."}
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_webhook_missing_required_fields(test_db_session, mocker):
    """
    Test that webhooks missing required fields (like timestamp) are rejected (422).
    """
    user_id = uuid.uuid4()
    
    class MockUser:
        def __init__(self, id, webhook_secret):
            self.id = id
            self.username = "test_user"
            self.webhook_secret = webhook_secret
            self.encrypted_api_keys = {"encrypted_data": "dummy"}
            self.exchange = "binance"
            self.risk_config = {}
            self.dca_grid_config = {}

    mock_user_instance = MockUser(id=user_id, webhook_secret="valid_secret")
    mocker.patch.object(UserRepository, "get_by_id", AsyncMock(return_value=mock_user_instance))

    app.dependency_overrides[get_db_session] = lambda: test_db_session

    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {
            "tv": {
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "entry_price": 50000,
                "action": "long",
                "market_position": "long",
                "market_position_size": 0.0,
                "prev_market_position": "flat",
                "prev_market_position_size": 0.0,
                "close_price": 50000,
                "order_size": 0.1
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "base",
                "precision_mode": "auto"
            },
            "strategy_info": {
                "trade_id": "test_trade",
                "alert_name": "test_alert",
                "alert_message": "test_message"
            },
            "risk": { "max_slippage_percent": 0.5 },
            "secret": "valid_secret", # Must be valid to pass auth and reach validation
            "source": "tradingview",
            "user_id": str(user_id)
            # Missing "timestamp"
        }
        json_payload = json.dumps(payload, separators=(',', ':'))
        headers = {
            "Content-Type": "application/json"
        }
        response = await ac.post(f"/api/v1/webhooks/{user_id}/tradingview", content=json_payload, headers=headers)
        
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_webhook_unreplaced_placeholders(test_db_session, mocker):
    """
    Test that webhooks with unreplaced TradingView placeholders (e.g. {{ticker}}) are rejected.
    """
    user_id = uuid.uuid4()
    
    class MockUser:
        def __init__(self, id, webhook_secret):
            self.id = id
            self.username = "test_user"
            self.webhook_secret = webhook_secret
            self.encrypted_api_keys = {"encrypted_data": "dummy"}
            self.exchange = "binance"
            self.risk_config = {}
            self.dca_grid_config = {}

    mock_user_instance = MockUser(id=user_id, webhook_secret="valid_secret")
    mocker.patch.object(UserRepository, "get_by_id", AsyncMock(return_value=mock_user_instance))
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {
            "tv": {
                "exchange": "binance",
                "symbol": "{{ticker}}", # Placeholder!
                "timeframe": 15,
                "entry_price": 50000,
                "action": "long",
                "market_position": "long",
                "market_position_size": 0.0,
                "prev_market_position": "flat",
                "prev_market_position_size": 0.0,
                "close_price": 50000,
                "order_size": 0.1
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "base",
                "precision_mode": "auto"
            },
            "strategy_info": {
                "trade_id": "test_trade",
                "alert_name": "test_alert",
                "alert_message": "test_message"
            },
            "risk": { "max_slippage_percent": 0.5 },
            "secret": "valid_secret", # Must be valid
            "source": "tradingview",
            "timestamp": "2023-01-01T00:00:00Z",
            "user_id": str(user_id)
        }
        json_payload = json.dumps(payload, separators=(',', ':'))
        headers = {
            "Content-Type": "application/json"
        }
        response = await ac.post(f"/api/v1/webhooks/{user_id}/tradingview", content=json_payload, headers=headers)
        assert response.status_code == 422
        
        payload["tv"]["entry_price"] = "{{close}}" # This will definitely fail float conversion
        json_payload = json.dumps(payload, separators=(',', ':'))
        response = await ac.post(f"/api/v1/webhooks/{user_id}/tradingview", content=json_payload, headers=headers)
        assert response.status_code == 422
    app.dependency_overrides = {}
