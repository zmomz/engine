import pytest
import uuid
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_user_invalid_email_format(client: AsyncClient):
    """Test registration with invalid email format."""
    user_data = {
        "username": "newuser",
        "email": "not-an-email",
        "password": "password123",
        "exchange": "binance",
        "webhook_secret": "secret"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 422 # Validation error from Pydantic

@pytest.mark.asyncio
async def test_register_user_missing_fields(client: AsyncClient):
    """Test registration with missing required fields."""
    user_data = {
        "username": "newuser",
        # Missing email and password
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_login_empty_credentials(client: AsyncClient):
    """Test login with empty credentials."""
    login_data = {"username": "", "password": ""}
    response = await client.post("/api/v1/users/login", data=login_data)
    # Typically 422 if validation fails on empty string, or 401 if it goes through but fails auth
    # FastAPI OAuth2PasswordRequestForm might return 422 for missing fields or 400
    assert response.status_code in [400, 422, 401]

@pytest.mark.asyncio
async def test_risk_block_invalid_uuid(authorized_client: AsyncClient, override_get_db_session_for_integration_tests):
    """Test blocking risk for an invalid UUID."""
    invalid_uuid = "not-a-uuid"
    response = await authorized_client.post(f"/api/v1/risk/{invalid_uuid}/block")
    assert response.status_code == 422 # Pydantic validation error for UUID

@pytest.mark.asyncio
async def test_risk_block_nonexistent_group(authorized_client: AsyncClient, override_get_db_session_for_integration_tests):
    """Test blocking risk for a non-existent position group."""
    random_uuid = str(uuid.uuid4())
    response = await authorized_client.post(f"/api/v1/risk/{random_uuid}/block")
    assert response.status_code == 404
    assert response.json()["detail"] == "PositionGroup not found"
