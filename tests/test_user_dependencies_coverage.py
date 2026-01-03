"""
Tests for api/dependencies/users.py to improve coverage.
Focuses on get_current_user, get_current_active_user, and check_token_blacklist.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request
from jose import jwt
import uuid
from datetime import datetime, timedelta

from app.api.dependencies.users import (
    get_current_user,
    get_current_active_user,
    check_token_blacklist,
    get_token_from_cookie,
    COOKIE_NAME
)
from app.core.security import SECRET_KEY, ALGORITHM
from app.models.user import User


class TestGetTokenFromCookie:
    """Tests for get_token_from_cookie function."""

    def test_extracts_token_with_bearer_prefix(self):
        """Test extracting token with Bearer prefix."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: "Bearer my_token_123"}

        token = get_token_from_cookie(mock_request)
        assert token == "my_token_123"

    def test_returns_none_without_bearer_prefix(self):
        """Test returns None when cookie doesn't have Bearer prefix."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: "my_token_123"}

        token = get_token_from_cookie(mock_request)
        assert token is None

    def test_returns_none_when_no_cookie(self):
        """Test returns None when cookie is not present."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        token = get_token_from_cookie(mock_request)
        assert token is None

    def test_returns_none_when_cookie_is_empty(self):
        """Test returns None when cookie value is empty string."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: ""}

        token = get_token_from_cookie(mock_request)
        assert token is None


class TestCheckTokenBlacklist:
    """Tests for check_token_blacklist function."""

    @pytest.mark.asyncio
    async def test_returns_true_when_token_blacklisted(self):
        """Test returns True when token is in blacklist."""
        with patch("app.api.dependencies.users.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.is_token_blacklisted = AsyncMock(return_value=True)
            mock_get_cache.return_value = mock_cache

            result = await check_token_blacklist("test_jti_123")

            assert result is True
            mock_cache.is_token_blacklisted.assert_called_once_with("test_jti_123")

    @pytest.mark.asyncio
    async def test_returns_false_when_token_not_blacklisted(self):
        """Test returns False when token is not in blacklist."""
        with patch("app.api.dependencies.users.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.is_token_blacklisted = AsyncMock(return_value=False)
            mock_get_cache.return_value = mock_cache

            result = await check_token_blacklist("test_jti_456")

            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_cache_error(self):
        """Test returns False (fail open) when cache is unavailable."""
        with patch("app.api.dependencies.users.get_cache") as mock_get_cache:
            mock_get_cache.side_effect = Exception("Redis unavailable")

            result = await check_token_blacklist("test_jti_789")

            # Should fail open - allow token through
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_blacklist_check_error(self):
        """Test returns False when blacklist check itself fails."""
        with patch("app.api.dependencies.users.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.is_token_blacklisted = AsyncMock(side_effect=Exception("Check failed"))
            mock_get_cache.return_value = mock_cache

            result = await check_token_blacklist("test_jti")

            # Should fail open
            assert result is False


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    def create_valid_token(self, username: str = "testuser", jti: str = None) -> str:
        """Helper to create valid JWT token."""
        if jti is None:
            jti = str(uuid.uuid4())
        payload = {
            "sub": username,
            "jti": jti,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @pytest.mark.asyncio
    async def test_extracts_token_from_header(self):
        """Test user is retrieved from header token."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}

        mock_user = MagicMock(spec=User)
        mock_user.username = "testuser"

        mock_db = AsyncMock()
        token = self.create_valid_token("testuser")

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist", return_value=False):
                user = await get_current_user(mock_request, token, mock_db)

                assert user == mock_user
                mock_repo.get_by_username.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_extracts_token_from_cookie_when_no_header(self):
        """Test user is retrieved from cookie when header token is None."""
        token = self.create_valid_token("cookie_user")

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: f"Bearer {token}"}

        mock_user = MagicMock(spec=User)
        mock_user.username = "cookie_user"

        mock_db = AsyncMock()

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist", return_value=False):
                user = await get_current_user(mock_request, None, mock_db)

                assert user == mock_user
                mock_repo.get_by_username.assert_called_once_with("cookie_user")

    @pytest.mark.asyncio
    async def test_raises_401_when_no_token(self):
        """Test HTTPException 401 when no token in header or cookie."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, None, mock_db)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_on_invalid_jwt(self):
        """Test HTTPException 401 on invalid JWT."""
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        invalid_token = "not_a_valid_jwt_token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, invalid_token, mock_db)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_username_missing_in_token(self):
        """Test HTTPException 401 when 'sub' claim is missing."""
        # Create token without 'sub' claim
        payload = {
            "jti": str(uuid.uuid4()),
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_request, token, mock_db)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_token_blacklisted(self):
        """Test HTTPException 401 when token is blacklisted."""
        jti = str(uuid.uuid4())
        token = self.create_valid_token("testuser", jti)

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        with patch("app.api.dependencies.users.check_token_blacklist", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request, token, mock_db)

            assert exc_info.value.status_code == 401
            assert "Token has been revoked" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_user_not_found(self):
        """Test HTTPException 401 when user doesn't exist in database."""
        token = self.create_valid_token("nonexistent_user")

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist", return_value=False):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(mock_request, token, mock_db)

                assert exc_info.value.status_code == 401
                assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_does_not_check_blacklist_when_no_jti(self):
        """Test blacklist check is skipped when token has no jti."""
        # Create token without jti
        payload = {
            "sub": "testuser",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        mock_user = MagicMock(spec=User)
        mock_user.username = "testuser"

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist") as mock_check:
                user = await get_current_user(mock_request, token, mock_db)

                # Blacklist check should not be called
                mock_check.assert_not_called()
                assert user == mock_user


class TestGetCurrentActiveUser:
    """Tests for get_current_active_user function."""

    @pytest.mark.asyncio
    async def test_returns_active_user(self):
        """Test returns user when user is active."""
        mock_user = MagicMock(spec=User)
        mock_user.is_active = True

        result = await get_current_active_user(mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_raises_400_when_user_inactive(self):
        """Test HTTPException 400 when user is inactive."""
        mock_user = MagicMock(spec=User)
        mock_user.is_active = False

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(mock_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail


class TestIntegration:
    """Integration tests for user authentication flow."""

    @pytest.mark.asyncio
    async def test_full_auth_flow_from_header(self):
        """Test complete authentication flow with header token."""
        jti = str(uuid.uuid4())
        payload = {
            "sub": "integration_user",
            "jti": jti,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        mock_user = MagicMock(spec=User)
        mock_user.username = "integration_user"
        mock_user.is_active = True

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist", return_value=False):
                user = await get_current_user(mock_request, token, mock_db)
                active_user = await get_current_active_user(user)

                assert active_user.username == "integration_user"
                assert active_user.is_active is True

    @pytest.mark.asyncio
    async def test_full_auth_flow_from_cookie(self):
        """Test complete authentication flow with cookie token."""
        jti = str(uuid.uuid4())
        payload = {
            "sub": "cookie_auth_user",
            "jti": jti,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {COOKIE_NAME: f"Bearer {token}"}
        mock_db = AsyncMock()

        mock_user = MagicMock(spec=User)
        mock_user.username = "cookie_auth_user"
        mock_user.is_active = True

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist", return_value=False):
                user = await get_current_user(mock_request, None, mock_db)  # No header token
                active_user = await get_current_active_user(user)

                assert active_user.username == "cookie_auth_user"

    @pytest.mark.asyncio
    async def test_auth_fails_for_inactive_user(self):
        """Test authentication fails at active_user check for inactive users."""
        jti = str(uuid.uuid4())
        payload = {
            "sub": "inactive_user",
            "jti": jti,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {}
        mock_db = AsyncMock()

        mock_user = MagicMock(spec=User)
        mock_user.username = "inactive_user"
        mock_user.is_active = False  # Inactive

        with patch("app.api.dependencies.users.UserRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_username = AsyncMock(return_value=mock_user)
            mock_repo_cls.return_value = mock_repo

            with patch("app.api.dependencies.users.check_token_blacklist", return_value=False):
                user = await get_current_user(mock_request, token, mock_db)

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_active_user(user)

                assert exc_info.value.status_code == 400
                assert "Inactive user" in exc_info.value.detail
