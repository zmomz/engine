"""Tests for Telegram API endpoints"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from app.main import app
from app.db.database import get_db_session
from app.models.user import User
from app.api.dependencies.users import get_current_active_user
import uuid


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.telegram_config = None
    return user


@pytest.fixture
def mock_user_with_config():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.telegram_config = {
        "enabled": True,
        "bot_token": "test_token",
        "channel_id": "-100123456",
        "channel_name": "Test Channel",
        "send_entry_signals": True,
        "send_exit_signals": True,
        "update_on_pyramid": True,
        "test_mode": True
    }
    return user


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.get = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


class TestTelegramAPI:
    """Tests for Telegram API endpoints"""

    @pytest.mark.asyncio
    async def test_get_telegram_config_no_config(self, mock_user, mock_db_session):
        """Test getting telegram config when none exists"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/telegram/config")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_telegram_config_with_config(self, mock_user_with_config, mock_db_session):
        """Test getting telegram config when config exists"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user_with_config
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/api/v1/telegram/config")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["bot_token"] == "test_token"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_telegram_config(self, mock_user, mock_db_session):
        """Test updating telegram config"""
        mock_db_user = MagicMock()
        mock_db_user.telegram_config = None
        mock_db_session.get = AsyncMock(return_value=mock_db_user)

        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.put(
                "/api/v1/telegram/config",
                json={
                    "enabled": True,
                    "bot_token": "new_token",
                    "channel_id": "-100999999"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["bot_token"] == "new_token"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_telegram_config_partial(self, mock_user_with_config, mock_db_session):
        """Test partial update of telegram config"""
        mock_db_user = MagicMock()
        mock_db_user.telegram_config = mock_user_with_config.telegram_config
        mock_db_session.get = AsyncMock(return_value=mock_db_user)

        app.dependency_overrides[get_current_active_user] = lambda: mock_user_with_config
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.put(
                "/api/v1/telegram/config",
                json={"enabled": False}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        # Other fields should be preserved
        assert data["bot_token"] == "test_token"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_connection_no_token(self, mock_user, mock_db_session):
        """Test connection test without bot token"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/telegram/test-connection",
                json={}
            )

        assert response.status_code == 400
        assert "Bot token not provided" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_user, mock_db_session):
        """Test successful connection test"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.telegram.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.test_connection = AsyncMock(return_value=(True, "OK"))
            MockBroadcaster.return_value = mock_broadcaster

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/telegram/test-connection",
                    json={"bot_token": "test_token", "channel_id": "-100123"}
                )

            assert response.status_code == 200
            assert response.json()["status"] == "success"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, mock_user, mock_db_session):
        """Test failed connection test"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.telegram.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.test_connection = AsyncMock(return_value=(False, "Invalid token"))
            MockBroadcaster.return_value = mock_broadcaster

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/telegram/test-connection",
                    json={"bot_token": "bad_token", "channel_id": "-100123"}
                )

            assert response.status_code == 400
            assert "Invalid token" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_test_connection_with_existing_config(self, mock_user_with_config, mock_db_session):
        """Test connection test merges with existing config"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user_with_config
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.telegram.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster.test_connection = AsyncMock(return_value=(True, "OK"))
            MockBroadcaster.return_value = mock_broadcaster

            async with AsyncClient(app=app, base_url="http://test") as ac:
                # Only provide partial config - should merge with existing
                response = await ac.post(
                    "/api/v1/telegram/test-connection",
                    json={"channel_id": "-100newchannel"}
                )

            assert response.status_code == 200

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_send_test_message_no_config(self, mock_user, mock_db_session):
        """Test sending test message without config"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/telegram/test-message")

        assert response.status_code == 400
        assert "configuration not set" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_send_test_message_missing_credentials(self, mock_db_session):
        """Test sending test message without bot token or channel"""
        mock_user = MagicMock(spec=User)
        mock_user.telegram_config = {"enabled": True}  # No token or channel

        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/api/v1/telegram/test-message")

        assert response.status_code == 400
        assert "Bot token and channel ID required" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_send_test_message_success(self, mock_user_with_config, mock_db_session):
        """Test successful test message send"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user_with_config
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.telegram.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster._send_message = AsyncMock(return_value=12345)
            MockBroadcaster.return_value = mock_broadcaster

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/telegram/test-message")

            assert response.status_code == 200
            assert response.json()["status"] == "success"
            assert response.json()["message_id"] == 12345

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_send_test_message_failure(self, mock_user_with_config, mock_db_session):
        """Test failed test message send"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user_with_config
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.telegram.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster._send_message = AsyncMock(return_value=None)
            MockBroadcaster.return_value = mock_broadcaster

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/telegram/test-message")

            assert response.status_code == 400
            assert "Failed to send test message" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_send_test_message_exception(self, mock_user_with_config, mock_db_session):
        """Test test message send with exception"""
        app.dependency_overrides[get_current_active_user] = lambda: mock_user_with_config
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        with patch('app.api.telegram.TelegramBroadcaster') as MockBroadcaster:
            mock_broadcaster = MagicMock()
            mock_broadcaster._send_message = AsyncMock(side_effect=Exception("Network error"))
            MockBroadcaster.return_value = mock_broadcaster

            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post("/api/v1/telegram/test-message")

            assert response.status_code == 400
            assert "Network error" in response.json()["detail"]

        app.dependency_overrides.clear()
