import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.schemas.user import UserCreate

@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "hashed_password" in data
    assert verify_password(user_data["password"], data["hashed_password"])

    # Verify user is in DB
    from app.repositories.user import UserRepository
    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_username("testuser")
    assert user is not None
    assert user.email == "test@example.com"

@pytest.mark.asyncio
async def test_register_user_duplicate_username(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    duplicate_user_data = {
        "username": "testuser",
        "email": "another@example.com",
        "password": "anotherpassword"
    }
    response = await client.post("/api/v1/users/register", json=duplicate_user_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}

@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    duplicate_email_data = {
        "username": "anotheruser",
        "email": "test@example.com",
        "password": "anotherpassword"
    }
    response = await client.post("/api/v1/users/register", json=duplicate_email_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}
