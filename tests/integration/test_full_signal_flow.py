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
from app.models.user import User

@pytest.mark.asyncio
async def test_full_signal_flow_new_position(
    http_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User
):
    """
    Tests the full signal flow for a new position:
    1. Clears the mock exchange state.
    2. Sends a valid webhook payload to the /api/webhooks/tradingview endpoint.
    3. Verifies that a new PositionGroup is created in the database.
    4. Verifies that the correct number of DCAOrder records are created.
    5. Verifies that the correct number of orders were placed on the mock exchange.
    """
    # 0. Clear mock exchange state before test
    async with httpx.AsyncClient() as client:
        await client.delete("http://mock-exchange:9000/test/orders")

    # 1. Send a valid webhook payload
    webhook_payload = {
        "user_id": str(test_user.id),
        "secret": "your-super-secret-key",
        "source": "tradingview",
        "timestamp": "2025-11-19T14:00:00Z",
        "tv": {
            "exchange": "MOCK",
            "symbol": "BTCUSDT",
            "timeframe": 15,
            "action": "long",
            "market_position": "long",
            "market_position_size": 1.0,
            "prev_market_position": "flat",
            "prev_market_position_size": 0.0,
            "entry_price": 50000.00,
            "close_price": 50000.00,
            "order_size": 1.0
        },
        "strategy_info": {
            "trade_id": "test_trade_123",
            "alert_name": "Test Alert",
            "alert_message": "Test alert message"
        },
        "execution_intent": {
            "type": "signal",
            "side": "buy",
            "position_size_type": "quote",
            "precision_mode": "auto"
        },
        "risk": {
            "stop_loss": 49000.00,
            "take_profit": 51000.00,
            "max_slippage_percent": 0.1
        }
    }
    payload_str = json.dumps(webhook_payload)
    secret = test_user.webhook_secret
    headers = {
        "X-Signature": generate_tradingview_signature(payload_str, secret)
    }

    response = await http_client.post(f"/api/v1/webhooks/{test_user.id}/tradingview", json=webhook_payload, headers=headers)
    assert response.status_code == 202, f"API call failed: {response.text}"

    # 2. Promote the signal from the queue to create the position group
    from app.services.queue_manager import QueueManagerService
    from app.repositories.queued_signal import QueuedSignalRepository
    from app.repositories.position_group import PositionGroupRepository
    from app.services.exchange_abstraction.factory import get_exchange_connector
    from app.services.execution_pool_manager import ExecutionPoolManager
    from app.services.position_manager import PositionManagerService
    from app.services.grid_calculator import GridCalculatorService
    from app.services.order_management import OrderService
    from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
    from decimal import Decimal

    exchange_connector = get_exchange_connector("mock")
    grid_calculator_service = GridCalculatorService()
    execution_pool_manager = ExecutionPoolManager(
        session=db_session,
        position_group_repository_class=PositionGroupRepository
    )
    position_manager_service = PositionManagerService(
        session=db_session,
        user=test_user,
        position_group_repository_class=PositionGroupRepository,
        grid_calculator_service=grid_calculator_service,
        order_service_class=OrderService,
        exchange_connector=exchange_connector
    )
    queue_manager = QueueManagerService(
        session=db_session,
        user=test_user,
        queued_signal_repository_class=QueuedSignalRepository,
        position_group_repository_class=PositionGroupRepository,
        exchange_connector=exchange_connector,
        execution_pool_manager=execution_pool_manager,
        position_manager_service=position_manager_service,
        grid_calculator_service=grid_calculator_service,
        order_service_class=OrderService,
        risk_engine_config=RiskEngineConfig(),
        dca_grid_config=DCAGridConfig.model_validate([
            {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
            {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
        ]),
        total_capital_usd=Decimal("10000")
    )
    await queue_manager.promote_highest_priority_signal()

    # 3. Verify database state
    await db_session.commit() # Ensure transaction is committed so we can read the data
    
    # Check PositionGroup
    result = await db_session.execute(select(PositionGroup).where(PositionGroup.user_id == test_user.id))
    position_group = result.scalars().first()
    assert position_group is not None
    assert position_group.symbol == "BTCUSDT"
    assert position_group.status == "live"
    
    # Check DCAOrders
    result = await db_session.execute(select(DCAOrder).where(DCAOrder.group_id == position_group.id))
    dca_orders = result.scalars().all()
    assert len(dca_orders) == 5 # Based on the default DCAGridConfig in conftest

    # 3. Verify mock exchange state
    async with httpx.AsyncClient() as client:
        exchange_orders_response = await client.get("http://mock-exchange:9000/test/orders")
    assert exchange_orders_response.status_code == 200
    exchange_orders = exchange_orders_response.json()
    
    assert len(exchange_orders) == 5
    first_order = exchange_orders[0]
    assert first_order["symbol"] == "BTCUSDT"
    assert first_order["side"] == "BUY"
    assert first_order["type"] == "LIMIT"