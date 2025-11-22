import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.user import User
from app.schemas.webhook_payloads import WebhookPayload
from app.services.queue_manager import QueueManagerService
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.position_manager import PositionManagerService
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService
from app.services.risk_engine import RiskEngineService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from decimal import Decimal
import json
import uuid
from datetime import datetime
from tests.integration.utils import generate_tradingview_signature

@pytest.mark.asyncio
async def test_exchange_api_timeout_on_order_submission(
    http_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    mock_exchange_connector: MagicMock # Using the fixture from conftest
):
    """
    Test that the system handles an exchange API timeout gracefully during order submission.
    """
    # 0. Set up mock exchange to simulate a TimeoutError
    mock_exchange_connector.submit_order.side_effect = TimeoutError("Simulated exchange timeout")
    
    # Patch the factory to return our configured mock
    with patch('app.services.exchange_abstraction.factory.get_exchange_connector', return_value=mock_exchange_connector):
        # 1. Send a valid webhook payload to trigger signal processing
        webhook_payload_data = {
            "user_id": str(test_user.id),
            "secret": "your-super-secret-key",
            "source": "tradingview",
            "timestamp": "2025-11-19T14:00:00Z",
            "tv": {
                "exchange": "MOCK", # Use MOCK exchange for this test
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
                "trade_id": "timeout_trade_123",
                "alert_name": "Timeout Test Alert",
                "alert_message": "Test alert message for timeout"
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "quote",
                "precision_mode": "auto"
            },
            "risk": {}
        }
        payload_str = json.dumps(webhook_payload_data)
        secret = test_user.webhook_secret
        headers = {
            "X-Signature": generate_tradingview_signature(payload_str, secret)
        }

        response = await http_client.post(f"/api/v1/webhooks/{test_user.id}/tradingview", json=webhook_payload_data, headers=headers)
        assert response.status_code == 202, f"API call failed: {response.text}"

        # 2. Manually promote the signal from the queue to attempt order submission
        # This will trigger the submit_order method on our mocked exchange_connector
        grid_calculator_service = GridCalculatorService()
        risk_engine_config = RiskEngineConfig()
        
        execution_pool_manager = ExecutionPoolManager(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository
        )
        position_manager_service = PositionManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=grid_calculator_service,
            order_service_class=OrderService,
            exchange_connector=mock_exchange_connector # Pass our mock
        )
        risk_engine_service = RiskEngineService(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository,
            risk_action_repository_class=RiskActionRepository,
            dca_order_repository_class=DCAOrderRepository,
            exchange_connector=mock_exchange_connector,
            order_service_class=OrderService,
            risk_engine_config=risk_engine_config
        )
        
        queue_manager = QueueManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            queued_signal_repository_class=QueuedSignalRepository,
            position_group_repository_class=PositionGroupRepository,
            exchange_connector=mock_exchange_connector, # Pass our mock
            execution_pool_manager=execution_pool_manager,
            position_manager_service=position_manager_service,
            risk_engine_service=risk_engine_service,
            grid_calculator_service=grid_calculator_service,
            order_service_class=OrderService,
            risk_engine_config=risk_engine_config,
            dca_grid_config=DCAGridConfig.model_validate([
                {"gap_percent": 0.0, "weight_percent": 100, "tp_percent": 1.0}
            ]), # Simplified config for this test
            total_capital_usd=Decimal("10000")
        )

        # Expect the TimeoutError to be caught internally, not raised here
        await queue_manager.promote_highest_priority_signal()

        # 3. Verify that the order submission was attempted and failed, and system state is consistent
        mock_exchange_connector.submit_order.assert_called_once()
        
        # Verify no PositionGroup or DCAOrder was created (or they are in an error state)
        from sqlalchemy.future import select
        position_groups = (await db_session.execute(select(PositionGroup).where(PositionGroup.user_id == test_user.id))).scalars().all()
        dca_orders = (await db_session.execute(select(DCAOrder).where(DCAOrder.user_id == test_user.id))).scalars().all()
        
        # Given a timeout, no position group should be successfully created.
        # The signal should remain in the queue or be marked as failed/errored,
        # but a new position group won't be made.
        assert len(position_groups) == 0
        assert len(dca_orders) == 0
        
        # Additionally, verify the signal status if possible (requires fetching from repo)
        queued_signals = (await db_session.execute(select(QueuedSignalRepository.model))).scalars().all()
        assert len(queued_signals) == 1
        assert queued_signals[0].status == "queued" # Signal should remain queued or be marked with an error status
        
