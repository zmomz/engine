import logging
from typing import List, Dict, Any, Optional
from threading import Thread
import json
from decimal import Decimal

from redis import Redis
from sqlalchemy.orm import Session

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal

from app.core.config import settings
from app.core.security import EncryptionService
from app.models.position_group import PositionGroup
from app.models.user import User
from app.models.queued_signal import QueuedSignal
from app.schemas.webhook_payloads import WebhookPayload

from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.precision_validator import PrecisionValidator


from app.services.order_management import OrderService
from app.services.queue_manager import QueueManagerService
from app.services.grid_calculator import GridCalculatorService


from app.repositories.position_group import PositionGroupRepository
from app.models.position_group import PositionGroupStatus
from app.models.dca_order import OrderType

from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

logger = logging.getLogger(__name__)

class SignalRouterService:
    """
    Service for routing a validated signal for a specific user.
    """
    def __init__(self, user: User, encryption_service: EncryptionService = None):
        self.user = user
        self.encryption_service = encryption_service or EncryptionService()
    async def route(self, signal: WebhookPayload, db_session: AsyncSession) -> str:
        """
        Routes the signal.
        """
        # Initialize Dependencies
        pg_repo = PositionGroupRepository(db_session)
        exec_pool = ExecutionPoolManager(AsyncSessionLocal, PositionGroupRepository)
        queue_service = QueueManagerService(AsyncSessionLocal, user=self.user, execution_pool_manager=exec_pool)
        
        # Initialize Exchange Connector
        
        target_exchange = signal.tv.exchange.lower()
        encrypted_data = self.user.encrypted_api_keys
        if isinstance(encrypted_data, dict):
             if target_exchange in encrypted_data:
                 encrypted_data = encrypted_data[target_exchange]
             elif "encrypted_data" not in encrypted_data:
                 logger.error(f"Signal Router: No keys configured for {target_exchange}")
                 return f"Configuration Error: No API keys for {signal.tv.exchange}"

        try:
            api_key, api_secret = self.encryption_service.decrypt_keys(encrypted_data)
            exchange = get_exchange_connector(target_exchange, api_key=api_key, secret_key=api_secret)
        except Exception as e:
            logger.error(f"Signal Router: Failed to decrypt keys for {target_exchange}: {e}")
            return f"Configuration Error: Failed to decrypt keys for {signal.tv.exchange}"
        
        # Precision Validation (Block if metadata missing)
        try:
            precision_rules = await exchange.get_precision_rules()
            validator = PrecisionValidator(precision_rules)
            if not validator.validate_symbol(signal.tv.symbol):
                return f"Validation Error: Metadata missing or incomplete for symbol {signal.tv.symbol}"
        except Exception as e:
            logger.error(f"Signal Router: Precision validation failed: {e}")
            return f"Validation Error: Failed to fetch precision rules: {e}"

        grid_calc = GridCalculatorService()
        
        pos_manager = PositionManagerService(
            session_factory=AsyncSessionLocal,
            user=self.user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=grid_calc,
            order_service_class=OrderService,
            exchange_connector=exchange
        )

        # 1. Check for Existing Active Group
        active_groups = await pg_repo.get_active_position_groups_for_user(self.user.id)
        existing_group = next((g for g in active_groups if g.symbol == signal.tv.symbol and g.timeframe == signal.tv.timeframe and g.side == signal.tv.action), None)

        # Load Configs
        risk_config = RiskEngineConfig(**self.user.risk_config)
        dca_config = DCAGridConfig.model_validate(self.user.dca_grid_config) # Use model_validate for V2
        
        # Fetch Capital (Try to get from exchange, fallback to default)
        total_capital = Decimal("1000")
        try:
            balance = await exchange.fetch_balance()
            # Standardized flat structure (e.g., {'USDT': 1000.0})
            # Handle legacy/standard CCXT nested structure if present (robustness)
            if "total" in balance and isinstance(balance["total"], dict):
                balance = balance["total"]

            if isinstance(balance, dict):
                total_capital = Decimal(str(balance.get('USDT', 1000)))
        except Exception as e:
             logger.warning(f"Failed to fetch balance, using default: {e}")

        # Map 'buy'/'sell' to 'long'/'short'
        raw_action = signal.tv.action.lower()
        if raw_action == "buy":
            signal_side = "long"
        elif raw_action == "sell":
            signal_side = "short"
        else:
            signal_side = raw_action # Fallback or error if needed

        if existing_group:
            # Pyramid Logic
            max_pyramids = 5 # Default as not in config schemas currently
            if existing_group.pyramid_count < max_pyramids:
                try:
                    # Create transient QueuedSignal
                    qs = QueuedSignal(
                        user_id=self.user.id,
                        exchange=signal.tv.exchange,
                        symbol=signal.tv.symbol,
                        timeframe=signal.tv.timeframe,
                        side=signal_side,
                        entry_price=Decimal(str(signal.tv.entry_price)),
                        signal_payload=signal.dict()
                    )
                    
                    await pos_manager.handle_pyramid_continuation(
                        session=db_session,
                        user_id=self.user.id,
                        signal=qs,
                        existing_position_group=existing_group,
                        risk_config=risk_config,
                        dca_grid_config=dca_config,
                        total_capital_usd=total_capital
                    )
                    # Commit handled by caller (main loop in API usually? No, route is called by API)
                    # API route has db_session injected. Dependencies usually commit? 
                    # `db` dependency in FastAPI with `yield` typically commits on exit if no exception.
                    # But explicit commit here is safer if we want immediate result.
                    await db_session.commit()
                    return f"Pyramid executed for {signal.tv.symbol}"
                except Exception as e:
                    logger.error(f"Pyramid execution failed: {e}")
                    return f"Pyramid execution failed: {e}"
            else:
                return "Max pyramids reached. Signal ignored."

        else:
            # New Position Logic
            slot_available = await exec_pool.request_slot()
            if slot_available:
                try:
                    qs = QueuedSignal(
                        user_id=self.user.id,
                        exchange=signal.tv.exchange,
                        symbol=signal.tv.symbol,
                        timeframe=signal.tv.timeframe,
                        side=signal_side,
                        entry_price=Decimal(str(signal.tv.entry_price)),
                        signal_payload=signal.dict()
                    )
                    
                    await pos_manager.create_position_group_from_signal(
                        session=db_session,
                        user_id=self.user.id,
                        signal=qs,
                        risk_config=risk_config,
                        dca_grid_config=dca_config,
                        total_capital_usd=total_capital
                    )
                    await db_session.commit()
                    return f"New position created for {signal.tv.symbol}"
                except Exception as e:
                    logger.error(f"New position execution failed: {e}")
                    return f"New position execution failed: {e}"
            else:
                # Add to Queue
                # Update the payload side to match 'long'/'short' before queuing? 
                # Or just update the model object. The model object takes 'side'.
                # The 'signal' passed to add_signal_to_queue is the payload object.
                # We should update the payload object or modify add_signal_to_queue.
                # Let's modify the payload object side to be safe.
                signal.tv.action = signal_side 
                await queue_service.add_signal_to_queue(signal)
                return f"Pool full. Signal queued for {signal.tv.symbol}"
