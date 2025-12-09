import logging
import os
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
        logger.info(f"Received signal for {signal.tv.symbol} ({signal.tv.action}) on {signal.tv.exchange} for user {self.user.id}")
        
        response_message = ""

        # Load Configs First
        # Load Configs
        user_risk_config = self.user.risk_config
        if isinstance(user_risk_config, list):
            logger.warning("User risk_config found as list. Using default RiskEngineConfig.")
            risk_config = RiskEngineConfig()
        else:
            if isinstance(user_risk_config, str):
                risk_config = RiskEngineConfig(**json.loads(user_risk_config))
            else:
                risk_config = RiskEngineConfig(**user_risk_config)

        # DCA Config Loading Strategy: Specific > Global Legacy
        from app.repositories.dca_configuration import DCAConfigurationRepository
        dca_config_repo = DCAConfigurationRepository(db_session)

        # Normalize pair format: BTCUSDT -> BTC/USDT
        normalized_pair = signal.tv.symbol
        if '/' not in normalized_pair and len(normalized_pair) > 3:
            # Assume last 4 chars are quote currency (USDT) or 3 chars (USD, BTC, ETH)
            if normalized_pair.endswith('USDT'):
                normalized_pair = normalized_pair[:-4] + '/' + normalized_pair[-4:]
            elif normalized_pair.endswith(('USD', 'BTC', 'ETH', 'BNB')):
                normalized_pair = normalized_pair[:-3] + '/' + normalized_pair[-3:]

        specific_config = await dca_config_repo.get_specific_config(
            user_id=self.user.id,
            pair=normalized_pair,
            timeframe=signal.tv.timeframe,
            exchange=signal.tv.exchange.lower()
        )
        
        if specific_config:
            logger.info(f"Using specific DCA configuration for {signal.tv.symbol} {signal.tv.timeframe}")
            # Map DB model to Pydantic Schema
            from enum import Enum as PyEnum
            dca_config = DCAGridConfig(
                levels=specific_config.dca_levels,
                tp_mode=specific_config.tp_mode.value if isinstance(specific_config.tp_mode, PyEnum) else specific_config.tp_mode,
                tp_aggregate_percent=Decimal(str(specific_config.tp_settings.get("tp_aggregate_percent", 0))),
                tp_pyramid_percent=Decimal(str(specific_config.tp_settings.get("tp_pyramid_percent", 0))),
                max_pyramids=specific_config.max_pyramids,
                entry_order_type=specific_config.entry_order_type.value if isinstance(specific_config.entry_order_type, PyEnum) else specific_config.entry_order_type,
                pyramid_specific_levels=specific_config.pyramid_specific_levels or {}
            )
        else:
            logger.error(f"No DCA configuration found for {signal.tv.symbol} {signal.tv.timeframe} (Exchange: {signal.tv.exchange})")
            return f"Configuration Error: No active DCA configuration for {signal.tv.symbol} on {signal.tv.timeframe}."
            
        logger.debug(f"Resolved DCA Config: {dca_config}")

        # Initialize Dependencies
        pg_repo = PositionGroupRepository(db_session)
        exec_pool = ExecutionPoolManager(AsyncSessionLocal, PositionGroupRepository, max_open_groups=risk_config.max_open_positions_global)
        queue_service = QueueManagerService(AsyncSessionLocal, user=self.user, execution_pool_manager=exec_pool)
        
        # Initialize Exchange Connector
        exchange: Optional[Any] = None
        try:
            target_exchange = signal.tv.exchange.lower()
            encrypted_data = self.user.encrypted_api_keys
            
            if isinstance(encrypted_data, dict):
                 if target_exchange in encrypted_data:
                     encrypted_data = encrypted_data[target_exchange]
                 elif "encrypted_data" not in encrypted_data:
                     logger.error(f"Signal Router: No keys configured for {target_exchange}")
                     return f"Configuration Error: No API keys for {signal.tv.exchange}"

            # Build exchange_config dict for the factory function
            exchange_config = {}
            if isinstance(encrypted_data, str):
                # Legacy format
                exchange_config = {"encrypted_data": encrypted_data}
            elif isinstance(encrypted_data, dict):
                exchange_config = encrypted_data
            else:
                # Should not happen based on previous logic but safe fallback
                logger.error(f"Signal Router: Unexpected encrypted_data format: {type(encrypted_data)}")
                return f"Configuration Error: Invalid key format for {target_exchange}"

            exchange = get_exchange_connector(target_exchange, exchange_config)
        except Exception as e:
            logger.error(f"Signal Router: Failed to initialize exchange connector for {target_exchange}: {e}")
            return f"Configuration Error: Failed to initialize exchange connector for {signal.tv.exchange}"
        
        try:
            # Precision Validation (Block if metadata missing)
            try:
                precision_rules = await exchange.get_precision_rules()
                validator = PrecisionValidator(precision_rules)
                if not validator.validate_symbol(signal.tv.symbol):
                    response_message = f"Validation Error: Metadata missing or incomplete for symbol {signal.tv.symbol}"
                    return response_message
            except Exception as e:
                import traceback
                logger.error(f"Signal Router: Precision validation failed: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                response_message = f"Validation Error: Failed to fetch precision rules: {e}"
                return response_message

            grid_calc = GridCalculatorService()
            
            pos_manager = PositionManagerService(
                session_factory=AsyncSessionLocal,
                user=self.user,
                position_group_repository_class=PositionGroupRepository,
                grid_calculator_service=grid_calc,
                order_service_class=OrderService
            )

            # 1. Check for Existing Active Group
            active_groups = await pg_repo.get_active_position_groups_for_user(self.user.id)
            logger.debug(f"DEBUG: Active groups found: {active_groups}")
            
            # --- Handle Exit Signal ---
            intent_type = signal.execution_intent.type.lower() if signal.execution_intent else "signal"
            if intent_type == "exit":
                # Determine target position side to close
                # If action is 'buy', we close 'long'. If 'sell', we close 'short'.
                target_side = "long" if signal.tv.action.lower() == "buy" else "short"
                
                group_to_close = next((g for g in active_groups if g.symbol == signal.tv.symbol and g.exchange == signal.tv.exchange and g.side == target_side), None)
                
                if group_to_close:
                    await pos_manager.handle_exit_signal(group_to_close.id)
                    response_message = f"Exit signal executed for {signal.tv.symbol}"
                else:
                    logger.warning(f"Exit signal received for {signal.tv.symbol} but no active {target_side} position found.")
                    response_message = f"No active {target_side} position found for {signal.tv.symbol} to exit."

            # --- Handle Entry/Pyramid Signal ---
            else: # intent_type != "exit"
                # Map 'buy'/'sell' to 'long'/'short' for entry matching
                raw_action = signal.tv.action.lower()
                if raw_action == "buy":
                    signal_side = "long"
                elif raw_action == "sell":
                    signal_side = "short"
                else:
                    signal_side = raw_action # Fallback

                existing_group = next((g for g in active_groups if g.symbol == signal.tv.symbol and g.exchange == signal.tv.exchange and g.timeframe == signal.tv.timeframe and g.side == signal_side), None)
                logger.debug(f"DEBUG: Existing group after next(): {existing_group}")
                
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

                # Apply Risk Config Limit (max exposure)
                if risk_config.max_total_exposure_usd:
                    max_exposure = Decimal(str(risk_config.max_total_exposure_usd))
                    if total_capital > max_exposure:
                        logger.info(f"Capping total capital {total_capital} to max exposure {max_exposure}")
                        total_capital = max_exposure

                # Define Helper for New Position Execution
                async def execute_new_position():
                    try:
                        qs = QueuedSignal(
                            user_id=self.user.id,
                            exchange=signal.tv.exchange.lower(),
                            symbol=signal.tv.symbol,
                            timeframe=signal.tv.timeframe,
                            side=signal_side,
                            entry_price=Decimal(str(signal.tv.entry_price)),
                            signal_payload=signal.model_dump(mode='json')
                        )
                        
                        new_position_group = await pos_manager.create_position_group_from_signal(
                            session=db_session,
                            user_id=self.user.id,
                            signal=qs,
                            risk_config=risk_config,
                            dca_grid_config=dca_config,
                            total_capital_usd=total_capital
                        )
                        await db_session.commit()
                        
                        if new_position_group.status == PositionGroupStatus.FAILED:
                            logger.warning(f"New position created for {signal.tv.symbol}, but order submission failed. Status: FAILED.")
                            return f"New position created for {signal.tv.symbol}, but order submission failed."
                        else:
                            logger.info(f"New position created for {signal.tv.symbol}. Status: {new_position_group.status.value}")
                            return f"New position created for {signal.tv.symbol}"
                    except Exception as e:
                        logger.error(f"New position execution failed: {e}")
                        return f"New position execution failed: {e}"

                # Define Helper for Pyramid Execution
                async def execute_pyramid(group):
                    try:
                        qs = QueuedSignal(
                            user_id=self.user.id,
                            exchange=signal.tv.exchange.lower(),
                            symbol=signal.tv.symbol,
                            timeframe=signal.tv.timeframe,
                            side=signal_side,
                            entry_price=Decimal(str(signal.tv.entry_price)),
                            signal_payload=signal.model_dump(mode='json')
                        )
                        
                        await pos_manager.handle_pyramid_continuation(
                            session=db_session,
                            user_id=self.user.id,
                            signal=qs,
                            existing_position_group=group,
                            risk_config=risk_config,
                            dca_grid_config=dca_config,
                            total_capital_usd=total_capital
                        )
                        await db_session.commit()
                        logger.info(f"Pyramid executed for {signal.tv.symbol}")
                        return f"Pyramid executed for {signal.tv.symbol}"
                    except Exception as e:
                        logger.error(f"Pyramid execution failed: {e}")
                        return f"Pyramid execution failed: {e}"

                # Define Helper for Queuing
                async def queue_signal(msg_prefix="Pool full."):
                    signal.tv.action = signal_side 
                    await queue_service.add_signal_to_queue(signal)
                    logger.info(f"{msg_prefix} Signal queued for {signal.tv.symbol}")
                    return f"{msg_prefix} Signal queued for {signal.tv.symbol}"

                if existing_group:
                    # Pyramid Logic Check
                    if existing_group.pyramid_count < dca_config.max_pyramids - 1:
                        # Check Priority Rules for Bypass
                        priority_rules = risk_config.priority_rules
                        bypass_enabled = priority_rules.priority_rules_enabled.get("same_pair_timeframe", False)
                        
                        slot_available = False
                        
                        if bypass_enabled:
                            logger.info(f"Pyramid bypass rule ENABLED. Granting implicit slot for {signal.tv.symbol}")
                            slot_available = True
                        else:
                            # Rule DISABLED: Must compete for a standard slot
                            logger.info(f"Pyramid bypass rule DISABLED. Requesting standard slot for {signal.tv.symbol}")
                            slot_available = await exec_pool.request_slot()
                        
                        if slot_available:
                            response_message = await execute_pyramid(existing_group)
                        else:
                            response_message = await queue_signal("Pool full (Rule Disabled).")
                    else:
                        response_message = "Max pyramids reached. Signal ignored."

                else:
                    # New Position Logic
                    slot_available = await exec_pool.request_slot()
                    if slot_available:
                        response_message = await execute_new_position()
                    else:
                        response_message = await queue_signal("Pool full.")
        finally:
            if exchange:
                await exchange.close()
        
        return response_message
