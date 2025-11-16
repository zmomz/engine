import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.db.database import get_db_session
from app.models.queued_signal import QueuedSignal
from app.db.types import GUID
import uuid

# Mock the get_db_session dependency for testing
@pytest.fixture
async def test_db_session():
    # This fixture will be replaced by a more comprehensive one later
    # For now, it's a placeholder to allow the app to start
    yield AsyncMock()

@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejection(test_db_session):
    """
    Test that webhooks with invalid signatures are rejected.
    """
    app.dependency_overrides[get_db_session] = lambda: test_db_session
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Simulate an invalid signature
        headers = {"X-Signature": "invalid_signature"}
        payload = {"key": "value"}
        response = await ac.post("/api/webhooks/tradingview", json=payload, headers=headers)

        assert response.status_code == 403
        assert response.json() == {"detail": "Invalid signature."}
    app.dependency_overrides = {}
