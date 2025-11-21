import pytest
from httpx import AsyncClient
from app.models.user import User

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
