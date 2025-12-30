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
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder
from app.models.dca_configuration import DCAConfiguration, EntryOrderType, TakeProfitMode
from decimal import Decimal
import json
import uuid
from datetime import datetime
from app.core.security import EncryptionService

@pytest.mark.asyncio
async def test_exchange_api_timeout_on_order_submission(
    http_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    override_get_db_session_for_integration_tests
):
    """
    Test that the system handles an exchange API timeout gracefully during order submission.
    """
    # Note: User's encrypted_api_keys already includes mock exchange from conftest

    # Create DCA configuration for the signal (required for promotion)
    dca_config = DCAConfiguration(
        id=uuid.uuid4(),
        user_id=test_user.id,
        pair="BTC/USDT",  # Will be normalized from BTCUSDT
        timeframe=15,
        exchange="mock",
        entry_order_type=EntryOrderType.LIMIT,
        dca_levels=[
            {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
            {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
            {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
        ],
        pyramid_specific_levels={},
        tp_mode=TakeProfitMode.PER_LEG,
        tp_settings={"tp_aggregate_percent": 0},
        max_pyramids=5,
        use_custom_capital=True,
        custom_capital_usd=Decimal("10000.0"),  # Sufficient capital for min qty requirements
        pyramid_custom_capitals={}
    )
    db_session.add(dca_config)
    await db_session.commit()

    # 0. Set up mock exchange to simulate a TimeoutError
    mock_exchange_connector = MagicMock()
    # We mock place_order because OrderService uses it
    mock_exchange_connector.place_order = AsyncMock(side_effect=TimeoutError("Simulated exchange timeout"))
    mock_exchange_connector.get_precision_rules = AsyncMock(return_value={
        "BTCUSDT": {
            "tick_size": Decimal("0.01"),
            "step_size": Decimal("0.001"),
            "min_notional": Decimal("10.0"),
            "min_qty": Decimal("0.00001")
        }
    })
    mock_exchange_connector.get_current_price = AsyncMock(return_value=Decimal("50000.00"))
    mock_exchange_connector.fetch_balance = AsyncMock(return_value={'total': {'USDT': 10000}})
    mock_exchange_connector.close = AsyncMock()  # Add close method
    
    # Mock ExecutionPoolManager.request_slot to return False in the API (SignalRouter)
    mock_exec_pool = MagicMock()
    mock_exec_pool.request_slot = AsyncMock(return_value=False)
    
    # Patch dependencies
    # Note: signal_router uses ExchangeConfigService, not get_exchange_connector directly
    with (
        patch('app.services.position.position_creator.get_exchange_connector', return_value=mock_exchange_connector),
        patch('app.services.position.position_manager.get_exchange_connector', return_value=mock_exchange_connector),
        patch('app.services.exchange_abstraction.factory.get_exchange_connector', return_value=mock_exchange_connector),
        patch('app.services.queue_manager.get_exchange_connector', return_value=mock_exchange_connector),
        patch('app.services.signal_router.ExchangeConfigService') as mock_config_service,
        patch('app.services.signal_router.ExecutionPoolManager', return_value=mock_exec_pool)
    ):
        # Configure ExchangeConfigService mock
        mock_config_service.get_connector.return_value = mock_exchange_connector
         
        # 1. Send a valid webhook payload to trigger signal processing
        webhook_payload_data = {
            "user_id": str(test_user.id),
            "secret": test_user.webhook_secret, # Use the actual secret
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
            "risk": {
                "max_slippage_percent": 0.5
            }
        }

        response = await http_client.post(f"/api/v1/webhooks/{test_user.id}/tradingview", json=webhook_payload_data)
        assert response.status_code == 202, f"API call failed: {response.text}"

        # Verify signal is in queue
        from sqlalchemy.future import select
        result_qs = await db_session.execute(select(QueuedSignal).where(QueuedSignal.user_id == test_user.id))
        queued_signals = result_qs.scalars().all()
        assert len(queued_signals) == 1

        # 2. Manually promote the signal
        grid_calculator_service = GridCalculatorService()
        risk_engine_config = RiskEngineConfig()
        
        # Use a real execution pool manager here (or one that returns True)
        execution_pool_manager = ExecutionPoolManager(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository
        )
        
        position_manager_service = PositionManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=grid_calculator_service,
            order_service_class=OrderService
        )
        
        queue_manager = QueueManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            queued_signal_repository_class=QueuedSignalRepository,
            position_group_repository_class=PositionGroupRepository,
            exchange_connector=mock_exchange_connector, 
            execution_pool_manager=execution_pool_manager,
            position_manager_service=position_manager_service,
            polling_interval_seconds=0.01
        )

        await queue_manager.promote_highest_priority_signal(session=db_session)

        # Commit to ensure changes are visible
        await db_session.commit()

        # 3. Verify
        # Expect place_order to have been called (and failed with TimeoutError)
        mock_exchange_connector.place_order.assert_called()

        # Re-execute select
        result = await db_session.execute(select(PositionGroup).where(PositionGroup.user_id == test_user.id))
        position_groups = result.scalars().all()
        
        assert len(position_groups) == 1
        assert position_groups[0].status == "failed"
        
        result_qs = await db_session.execute(select(QueuedSignal).where(QueuedSignal.user_id == test_user.id))
        queued_signals = result_qs.scalars().all()
        assert len(queued_signals) == 1
        assert queued_signals[0].status == "promoted"