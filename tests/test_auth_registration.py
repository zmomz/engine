import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.security import verify_password

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    data = response.json()
    assert "id" in data
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "hashed_password" not in data

    # Verify user in database
    user = await db_session.get(User, data["id"])
    assert user is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert verify_password("testpassword", user.hashed_password)

@pytest.mark.asyncio
async def test_register_existing_user(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "username": "existinguser",
        "email": "existing@example.com",
        "password": "testpassword"
    }
    await client.post("/api/v1/users/register", json=user_data) # Register first time

    response = await client.post("/api/v1/users/register", json=user_data) # Register again
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}

@pytest.mark.asyncio
async def test_register_user_invalid_email(client: AsyncClient):
    user_data = {
        "username": "invalidemailuser",
        "email": "invalid-email",
        "password": "testpassword"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 422 # Unprocessable Entity for validation errors

@pytest.mark.asyncio
async def test_register_user_missing_fields(client: AsyncClient):
    user_data = {
        "username": "missingfielduser",
        "password": "testpassword"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 422 # Unprocessable Entity for validation errors
