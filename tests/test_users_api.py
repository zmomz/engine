import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, create_access_token
from app.schemas.user import UserCreate
from app.repositories.user import UserRepository

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
    assert "id" in data
    assert data["is_active"] is True
    assert data["is_superuser"] is False

    # Verify user is in DB
    user_repo = UserRepository(db_session)
    user_in_db = await user_repo.get_by_username("testuser")
    assert user_in_db is not None
    assert user_in_db.email == "test@example.com"

@pytest.mark.asyncio
async def test_register_user_duplicate_username(client: AsyncClient, db_session: AsyncSession):
    user_data = {
        "username": "duplicateuser",
        "email": "duplicate@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}

@pytest.mark.asyncio
async def test_register_user_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    user_data_1 = {
        "username": "user1",
        "email": "duplicate_email@example.com",
        "password": "securepassword"
    }
    user_data_2 = {
        "username": "user2",
        "email": "duplicate_email@example.com",
        "password": "anotherpassword"
    }
    await client.post("/api/v1/users/register", json=user_data_1)
    response = await client.post("/api/v1/users/register", json=user_data_2)
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}

@pytest.mark.asyncio
async def test_login_user_success(client: AsyncClient, db_session: AsyncSession):
    # Register a user first
    user_data = {
        "username": "testloginuser",
        "email": "testlogin@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    # Attempt to login
    login_data = {
        "username": "testloginuser",
        "password": "securepassword"
    }
    response = await client.post("/api/v1/users/login", data=login_data) # Use data for OAuth2PasswordRequestForm
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_user_invalid_credentials(client: AsyncClient, db_session: AsyncSession):
    # Register a user first
    user_data = {
        "username": "testinvaliduser",
        "email": "testinvalid@example.com",
        "password": "securepassword"
    }
    await client.post("/api/v1/users/register", json=user_data)

    # Attempt to login with wrong password
    login_data = {
        "username": "testinvaliduser",
        "password": "wrongpassword"
    }
    response = await client.post("/api/v1/users/login", data=login_data)
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}

@pytest.mark.asyncio
async def test_login_user_not_found(client: AsyncClient, db_session: AsyncSession):
    # Attempt to login with a non-existent user
    login_data = {
        "username": "nonexistentuser",
        "password": "anypassword"
    }
    response = await client.post("/api/v1/users/login", data=login_data)
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}