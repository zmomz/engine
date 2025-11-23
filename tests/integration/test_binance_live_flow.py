import pytest
import os
import json
import asyncio
import httpx
import ccxt.async_support as ccxt
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.position_group import PositionGroup
from app.models.dca_order import DCAOrder
from app.models.user import User
from tests.integration.utils import generate_tradingview_signature
from app.core.security import EncryptionService

# Constants for Binance Testnet
BINANCE_TESTNET_API_KEY = os.getenv("TEST_BINANCE_API_KEY")
BINANCE_TESTNET_SECRET_KEY = os.getenv("TEST_BINANCE_SECRET_KEY")

@pytest.mark.skipif(
    not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY,
    reason="Binance Testnet credentials not found in environment variables."
)
@pytest.mark.asyncio
async def test_binance_live_flow(
    http_client: httpx.AsyncClient,
    db_session: AsyncSession,
    test_user: User
):
    """
    Tests the full flow against the ACTUAL Binance Testnet.
    """
    # 0. Cleanup: Cancel open orders on Binance Testnet for this pair to start fresh
    print("\n[Setup] Connecting to Binance Testnet to fetch price and cleanup...")
    exchange = ccxt.binance({
        'apiKey': BINANCE_TESTNET_API_KEY,
        'secret': BINANCE_TESTNET_SECRET_KEY,
        'options': {'defaultType': 'spot'},
    })
    exchange.set_sandbox_mode(True)
    
    symbol = "BTC/USDT"
    tv_symbol = "BTCUSDT"
    
    try:
        # Cancel existing orders
        try:
            await exchange.cancel_all_orders(symbol)
            print("[Setup] Cancelled all open orders.")
        except Exception as e:
            print(f"[Setup] No orders to cancel or error cancelling: {e}")

        # Get current price to place realistic Limit orders
        ticker = await exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"[Setup] Current {symbol} Price: {current_price}")
        
        # Set entry price slightly below market for Long (so they sit as Limit orders)
        # If price is 50,000, entry at 49,000
        entry_price = float(current_price) * 0.98 
        
    finally:
        await exchange.close()

    # 1. Patch EncryptionService to return real keys
    # We do this because we haven't implemented the actual encryption in the DB yet
    # and we want the PositionManagerService to get the real keys when it "decrypts".
    with patch.object(EncryptionService, 'decrypt_keys', return_value=(BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_SECRET_KEY)):
        
        # 2. Send Webhook
        # We use the provided test_user but update its exchange preference conceptually (though the connector uses the keys)
        webhook_payload = {
            "user_id": str(test_user.id),
            "secret": "your-super-secret-key",
            "source": "tradingview",
            "timestamp": "2025-11-19T14:00:00Z",
            "tv": {
                "exchange": "BINANCE", # Important: Matches factory logic
                "symbol": tv_symbol,
                "timeframe": 15,
                "action": "long",
                "market_position": "long",
                "market_position_size": 1.0,
                "prev_market_position": "flat",
                "prev_market_position_size": 0.0,
                "entry_price": entry_price,
                "close_price": entry_price,
                "order_size": 1.0
            },
            "strategy_info": {
                "trade_id": "test_binance_live_1",
                "alert_name": "Binance Live Test",
                "alert_message": "Testing integration"
            },
            "execution_intent": {
                "type": "signal",
                "side": "buy",
                "position_size_type": "quote",
                "precision_mode": "auto"
            },
            "risk": {
                "stop_loss": entry_price * 0.95,
                "take_profit": entry_price * 1.05,
                "max_slippage_percent": 0.1
            }
        }
        
        payload_str = json.dumps(webhook_payload)
        headers = {
            "X-Signature": generate_tradingview_signature(payload_str, test_user.webhook_secret)
        }

        print("[Test] Sending Webhook...")
        response = await http_client.post(f"/api/v1/webhooks/{test_user.id}/tradingview", json=webhook_payload, headers=headers)
        assert response.status_code == 202, f"Webhook failed: {response.text}"

        # 3. Manually trigger Queue Processing
        # We need to replicate the setup from the previous test but ensure we use the factory that respects env vars
        from app.services.queue_manager import QueueManagerService
        from app.repositories.queued_signal import QueuedSignalRepository
        from app.repositories.position_group import PositionGroupRepository
        from app.repositories.risk_action import RiskActionRepository
        from app.repositories.dca_order import DCAOrderRepository
        from app.services.exchange_abstraction.factory import get_exchange_connector
        from app.services.execution_pool_manager import ExecutionPoolManager
        from app.services.position_manager import PositionManagerService
        from app.services.grid_calculator import GridCalculatorService
        from app.services.order_management import OrderService
        from app.services.risk_engine import RiskEngineService
        from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

        # Note: We don't need to pass keys here, the service fetches them from the user (which we mocked above)
        # But we DO need to ensure the factory uses testnet. We will set the ENV var for the test process.
        os.environ["EXCHANGE_TESTNET"] = "true"
        os.environ["EXCHANGE_DEFAULT_TYPE"] = "spot"

        # We need a connector instance for the QueueManager (it uses it for some checks, though mostly PositionManager does the heavy lifting)
        # Ideally QueueManager shouldn't need a specific connector instance bound at init if it's dynamic, 
        # but for this test structure it does.
        # However, PositionManager creates its OWN connector dynamically based on the signal.
        # The one passed to QueueManager is a default/fallback.
        exchange_connector = get_exchange_connector("binance", BINANCE_TESTNET_API_KEY, BINANCE_TESTNET_SECRET_KEY, default_type="spot")

        grid_calculator_service = GridCalculatorService()
        execution_pool_manager = ExecutionPoolManager(session_factory=lambda: db_session, position_group_repository_class=PositionGroupRepository)
        risk_engine_config = RiskEngineConfig()

        position_manager_service = PositionManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=grid_calculator_service,
            order_service_class=OrderService,
            exchange_connector=exchange_connector 
        )
        
        risk_engine_service = RiskEngineService(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository,
            risk_action_repository_class=RiskActionRepository,
            dca_order_repository_class=DCAOrderRepository,
            exchange_connector=exchange_connector,
            order_service_class=OrderService,
            risk_engine_config=risk_engine_config
        )

        queue_manager = QueueManagerService(
            session_factory=lambda: db_session,
            user=test_user,
            queued_signal_repository_class=QueuedSignalRepository,
            position_group_repository_class=PositionGroupRepository,
            exchange_connector=exchange_connector,
            execution_pool_manager=execution_pool_manager,
            position_manager_service=position_manager_service
        )

        print("[Test] Promoting signal...")
        await queue_manager.promote_highest_priority_signal()
        
        # 4. Verify DB
        await db_session.commit()
        result = await db_session.execute(select(PositionGroup).where(PositionGroup.user_id == test_user.id))
        position_group = result.scalars().first()
        assert position_group is not None
        assert position_group.status == "live"
        print(f"[Test] PositionGroup Created: {position_group.id}")

        result = await db_session.execute(select(DCAOrder).where(DCAOrder.group_id == position_group.id))
        dca_orders = result.scalars().all()
        assert len(dca_orders) > 0
        print(f"[Test] Created {len(dca_orders)} DCA orders in DB.")

        # 5. Verify Exchange (Binance Testnet)
        print("[Test] Verifying orders on Binance Testnet...")
        open_orders = await exchange.fetch_open_orders(symbol)
        print(f"[Test] Open Orders on Exchange: {len(open_orders)}")
        
        # We expect at least the amount of DCA orders we created (assuming no immediate fills)
        # Note: If price moved fast, some might have filled or not placed due to filters, but we check > 0
        assert len(open_orders) > 0
        
        # Cleanup
        await exchange.cancel_all_orders(symbol)
        await exchange.close()
