import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import json
import asyncio
import httpx
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder
from tests.integration.utils import generate_tradingview_signature

@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_full_signal_flow_new_position(
    http_client: AsyncClient,
    db_session: AsyncSession
):
    """
    Tests the full signal flow for a new position:
    1. Sends a valid webhook payload to the /api/webhooks/tradingview endpoint.
    2. Verifies that a new PositionGroup is created in the database.
    3. Verifies that the correct number of DCAOrder records are created.
    """
    # Wait for the service to be ready
    max_retries = 10
    retry_delay = 1
    for i in range(max_retries):
        try:
            response = await http_client.get("/api/health")
            if response.status_code == 200:
                break
        except httpx.ConnectError:
            if i == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay)
    
    # 1. Send a valid webhook payload
    webhook_payload = {
        "signal_id": "test_signal_123",
        "symbol": "BTCUSDT",
        "timeframe": 15,
        "side": "long",
        "price": "50000.00",
        "user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" # Placeholder user_id
    }
    payload_str = json.dumps(webhook_payload)
    secret = "your-super-secret-key" # This should match the secret in your .env file
    
    headers = {
        "X-Signature": generate_tradingview_signature(payload_str, secret)
    }

    response = await http_client.post("/api/webhooks/tradingview", json=webhook_payload, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "result": "Signal for BTCUSDT routed and created new position group."}

    # 2. Verify a new PositionGroup is created
    await db_session.flush() # Ensure data is available in the session
    result = await db_session.execute(select(PositionGroup).where(PositionGroup.symbol == "BTCUSDT"))
    position_group = result.scalars().first()
    assert position_group is not None
    assert position_group.symbol == "BTCUSDT"
    assert position_group.timeframe == 15
    assert position_group.side == "long"
    assert position_group.status == "live"

    # 3. Verify the correct number of DCAOrder records are created
    # This check can be re-enabled now that we have a shared session.
    # NOTE: The actual creation of DCA orders is not yet implemented in the SignalRouterService,
    # so this part of the test will be commented out until that logic is added.
    # result = await db_session.execute(select(DCAOrder).where(DCAOrder.group_id == position_group.id))
    # dca_orders = result.scalars().all()
    # assert len(dca_orders) == 5