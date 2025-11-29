import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.models.user import User
from app.schemas.user import UserUpdate, UserRead

@pytest.fixture
def mock_encryption_service():
    with patch("app.api.settings.EncryptionService") as MockEncryptionService:
        mock_instance = MockEncryptionService.return_value
        mock_instance.encrypt_keys.return_value = {"encrypted_api_key": "mock_encrypted_key", "encrypted_secret_key": "mock_encrypted_secret"}
        yield mock_instance

@pytest.mark.asyncio
async def test_get_supported_exchanges(
    authorized_client: AsyncClient,
    test_user: User
):
    response = await authorized_client.get("/api/v1/settings/exchanges")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "binance" in data
    assert "bybit" in data
    assert "mock" in data

@pytest.mark.asyncio
async def test_update_settings_no_api_keys(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    update_data = {"is_active": False}
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user_data = response.json()
    assert updated_user_data["is_active"] == False
    assert mock_encryption_service.encrypt_keys.call_count == 0

@pytest.mark.asyncio
async def test_update_settings_with_new_api_keys_target_exchange(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    update_data = {
        "api_key": "new_api_key",
        "secret_key": "new_secret_key",
        "key_target_exchange": "bybit",
        "testnet": True,
        "account_type": "UNIFIED"
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert updated_user.configured_exchange_details is not None
    assert "bybit" in updated_user.configured_exchange_details
    assert updated_user.configured_exchange_details["bybit"]["testnet"] is True
    assert updated_user.configured_exchange_details["bybit"]["account_type"] == "UNIFIED"
    mock_encryption_service.encrypt_keys.assert_called_once_with("new_api_key", "new_secret_key")

@pytest.mark.asyncio
async def test_update_settings_with_new_api_keys_user_update_exchange(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    update_data = {
        "api_key": "new_api_key_2",
        "secret_key": "new_secret_key_2",
        "exchange": "mock",
        "testnet": False, # Mock exchange usually not testnet
        "account_type": "SPOT" # Example for mock
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert updated_user.configured_exchange_details is not None
    assert "mock" in updated_user.configured_exchange_details
    assert updated_user.configured_exchange_details["mock"]["testnet"] is False
    assert updated_user.configured_exchange_details["mock"]["account_type"] == "SPOT"
    mock_encryption_service.encrypt_keys.assert_called_once_with("new_api_key_2", "new_secret_key_2")

@pytest.mark.asyncio
async def test_update_settings_with_new_api_keys_current_user_exchange(
    authorized_client: AsyncClient,
    test_user: User, # Assuming test_user has a default exchange like 'binance'
    mock_encryption_service: AsyncMock
):
    update_data = {
        "api_key": "new_api_key_3",
        "secret_key": "new_secret_key_3",
        "testnet": True, # Example
        "account_type": "UNIFIED" # Example
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert updated_user.configured_exchange_details is not None
    assert "binance" in updated_user.configured_exchange_details # Assuming default test_user exchange is 'binance'
    assert updated_user.configured_exchange_details["binance"]["testnet"] is True
    assert updated_user.configured_exchange_details["binance"]["account_type"] == "UNIFIED"
    mock_encryption_service.encrypt_keys.assert_called_once_with("new_api_key_3", "new_secret_key_3")

@pytest.mark.asyncio
async def test_delete_exchange_key_success(
    authorized_client: AsyncClient,
    test_user: User,
    db_session: AsyncMock # Added db_session to the fixture list
):
    # Ensure the user has an API key for 'mock' exchange
    test_user.encrypted_api_keys = {"mock": {"encrypted_api_key": "mock_key", "encrypted_secret_key": "mock_secret"}}
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await authorized_client.delete("/api/v1/settings/keys/mock")
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert "mock" not in updated_user.configured_exchanges

@pytest.mark.asyncio
async def test_delete_exchange_key_non_existent(
    authorized_client: AsyncClient,
    test_user: User
):
    # Ensure the user has no API keys initially, or no key for 'nonexistent'
    test_user.encrypted_api_keys = {"binance": {"encrypted_api_key": "bin_key", "encrypted_secret_key": "bin_secret"}} # Example
    response = await authorized_client.delete("/api/v1/settings/keys/nonexistent")
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert "nonexistent" not in updated_user.configured_exchanges
    assert "binance" in updated_user.configured_exchanges # Ensure other keys are untouched
