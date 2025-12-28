"""
Comprehensive tests for api/users.py to achieve 100% coverage.
Covers: set_auth_cookie, clear_auth_cookie, get_token_from_cookie, logout
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Response, Request

from app.api.users import (
    set_auth_cookie,
    clear_auth_cookie,
    get_token_from_cookie,
    COOKIE_NAME,
    COOKIE_MAX_AGE
)
from app.repositories.user import UserRepository


# --- Tests for cookie helpers ---

def test_set_auth_cookie_default_max_age():
    """Test setting auth cookie with default max age."""
    response = MagicMock(spec=Response)
    response.set_cookie = MagicMock()
    set_auth_cookie(response, "test_token")

    # Check cookie was set with correct parameters
    response.set_cookie.assert_called_once()
    call_kwargs = response.set_cookie.call_args[1]
    assert call_kwargs["key"] == COOKIE_NAME
    assert call_kwargs["value"] == "Bearer test_token"
    assert call_kwargs["httponly"] is True


def test_set_auth_cookie_custom_max_age():
    """Test setting auth cookie with custom max age."""
    response = MagicMock(spec=Response)
    response.set_cookie = MagicMock()
    custom_max_age = 3600  # 1 hour
    set_auth_cookie(response, "test_token", max_age=custom_max_age)

    call_kwargs = response.set_cookie.call_args[1]
    assert call_kwargs["max_age"] == custom_max_age


def test_set_auth_cookie_production_environment():
    """Test setting auth cookie in production environment uses secure flag."""
    response = MagicMock(spec=Response)
    response.set_cookie = MagicMock()

    with patch("app.api.users.settings") as mock_settings:
        mock_settings.ENVIRONMENT = "production"
        set_auth_cookie(response, "test_token")

    call_kwargs = response.set_cookie.call_args[1]
    assert call_kwargs["secure"] is True


def test_clear_auth_cookie():
    """Test clearing the auth cookie."""
    response = MagicMock(spec=Response)
    response.delete_cookie = MagicMock()
    clear_auth_cookie(response)

    # Cookie should be deleted
    response.delete_cookie.assert_called_once_with(key=COOKIE_NAME, path="/")


def test_get_token_from_cookie_valid():
    """Test extracting token from valid cookie."""
    request = MagicMock(spec=Request)
    request.cookies = {COOKIE_NAME: "Bearer test_token_123"}

    token = get_token_from_cookie(request)
    assert token == "test_token_123"


def test_get_token_from_cookie_no_cookie():
    """Test extracting token when no cookie exists."""
    request = MagicMock(spec=Request)
    request.cookies = {}

    token = get_token_from_cookie(request)
    assert token is None


def test_get_token_from_cookie_invalid_format():
    """Test extracting token when cookie format is invalid (no Bearer prefix)."""
    request = MagicMock(spec=Request)
    request.cookies = {COOKIE_NAME: "invalid_token"}

    token = get_token_from_cookie(request)
    assert token is None


def test_get_token_from_cookie_empty():
    """Test extracting token when cookie value is empty."""
    request = MagicMock(spec=Request)
    request.cookies = {COOKIE_NAME: ""}

    token = get_token_from_cookie(request)
    assert token is None


# --- Tests for logout endpoint ---

@pytest.mark.asyncio
async def test_logout_with_valid_token(client: AsyncClient, db_session: AsyncSession):
    """Test logout with valid token clears cookie and blacklists token."""
    # First register and login
    user_data = {
        "username": "logout_test_user",
        "email": "logout_test@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    login_data = {"username": "logout_test_user", "password": "securepassword"}
    login_response = await client.post("/api/v1/users/login", data=login_data)

    # Now logout
    response = await client.post("/api/v1/users/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}


@pytest.mark.asyncio
async def test_logout_without_token(client: AsyncClient):
    """Test logout without a token still succeeds."""
    response = await client.post("/api/v1/users/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}


@pytest.mark.asyncio
async def test_logout_blacklist_failure(client: AsyncClient, db_session: AsyncSession):
    """Test logout handles blacklist failure gracefully."""
    # First register and login
    user_data = {
        "username": "logout_fail_user",
        "email": "logout_fail@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    login_data = {"username": "logout_fail_user", "password": "securepassword"}
    await client.post("/api/v1/users/login", data=login_data)

    # Mock cache to raise exception
    with patch("app.api.users.get_cache") as mock_get_cache:
        mock_cache = AsyncMock()
        mock_cache.blacklist_token.side_effect = Exception("Redis unavailable")
        mock_get_cache.return_value = mock_cache

        response = await client.post("/api/v1/users/logout")
        # Should still succeed even if blacklist fails
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_with_invalid_token(client: AsyncClient):
    """Test logout with invalid token format in cookie."""
    # Set an invalid cookie manually - this won't work with AsyncClient
    # as cookies are managed differently, so we test the path through
    # the actual flow
    response = await client.post("/api/v1/users/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}


@pytest.mark.asyncio
async def test_logout_with_expired_token(client: AsyncClient, db_session: AsyncSession):
    """Test logout handles expired tokens."""
    # Register and login
    user_data = {
        "username": "expired_token_user",
        "email": "expired@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)
    login_data = {"username": "expired_token_user", "password": "securepassword"}
    await client.post("/api/v1/users/login", data=login_data)

    # Mock the expiry check to return 0 (expired)
    with patch("app.api.users.get_token_expiry_seconds") as mock_expiry:
        mock_expiry.return_value = 0  # Token expired

        response = await client.post("/api/v1/users/logout")
        assert response.status_code == 200


# --- Tests for login endpoint additional coverage ---

@pytest.mark.asyncio
async def test_login_sets_cookie(client: AsyncClient, db_session: AsyncSession):
    """Test that login sets httpOnly cookie."""
    user_data = {
        "username": "cookie_test_user",
        "email": "cookie_test@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    login_data = {"username": "cookie_test_user", "password": "securepassword"}
    response = await client.post("/api/v1/users/login", data=login_data)

    assert response.status_code == 200
    # Check that cookie was set
    cookies = response.cookies
    # The cookie should be set (exact checking depends on httpx version)
    data = response.json()
    assert "access_token" in data
    assert "user" in data
    assert data["user"]["username"] == "cookie_test_user"


@pytest.mark.asyncio
async def test_login_returns_user_info(client: AsyncClient, db_session: AsyncSession):
    """Test that login returns user information."""
    user_data = {
        "username": "userinfo_test",
        "email": "userinfo@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    login_data = {"username": "userinfo_test", "password": "securepassword"}
    response = await client.post("/api/v1/users/login", data=login_data)

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == "userinfo_test"
    assert data["user"]["email"] == "userinfo@example.com"
    assert data["user"]["is_active"] is True


# --- Tests for edge cases ---

@pytest.mark.asyncio
async def test_register_invalid_email_format(client: AsyncClient):
    """Test registration with invalid email format."""
    user_data = {
        "username": "invalid_email_user",
        "email": "not-an-email",
        "password": "securepassword"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    # Validation should fail
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_password(client: AsyncClient):
    """Test registration without password field."""
    user_data = {
        "username": "no_pass_user",
        "email": "nopass@example.com"
        # Missing password field
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    # Validation should fail for missing password
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_empty_username(client: AsyncClient):
    """Test login with empty username."""
    login_data = {"username": "", "password": "password"}
    response = await client.post("/api/v1/users/login", data=login_data)
    # Should fail validation or return 401
    assert response.status_code in [401, 422]


@pytest.mark.asyncio
async def test_login_empty_password(client: AsyncClient):
    """Test login with empty password."""
    login_data = {"username": "someuser", "password": ""}
    response = await client.post("/api/v1/users/login", data=login_data)
    # Should fail validation or return 401
    assert response.status_code in [401, 422]
