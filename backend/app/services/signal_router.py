import asyncio
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
from app.core.cache import get_cache

from app.core.config import settings
from app.core.security import EncryptionService
from app.models.position_group import PositionGroup
from app.models.user import User
from app.models.queued_signal import QueuedSignal
from app.schemas.webhook_payloads import WebhookPayload

from app.services.position_manager import PositionManagerService, DuplicatePositionException
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.exchange_config_service import ExchangeConfigService, ExchangeConfigError
from app.services.precision_validator import PrecisionValidator


from app.services.order_management import OrderService
from app.services.queue_manager import QueueManagerService
from app.services.grid_calculator import GridCalculatorService


from app.repositories.position_group import PositionGroupRepository
from app.models.position_group import PositionGroupStatus
from app.models.dca_order import OrderType

from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.services.risk.risk_engine import RiskEngineService
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository

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

        # DCA Config Loading Strategy: Cache > DB
        from app.repositories.dca_configuration import DCAConfigurationRepository

        # Normalize pair format: BTCUSDT -> BTC/USDT
        normalized_pair = signal.tv.symbol
        if '/' not in normalized_pair and len(normalized_pair) > 3:
            # Assume last 4 chars are quote currency (USDT) or 3 chars (USD, BTC, ETH)
            if normalized_pair.endswith('USDT'):
                normalized_pair = normalized_pair[:-4] + '/' + normalized_pair[-4:]
            elif normalized_pair.endswith(('USD', 'BTC', 'ETH', 'BNB')):
                normalized_pair = normalized_pair[:-3] + '/' + normalized_pair[-3:]

        target_exchange = signal.tv.exchange.lower()
        user_id_str = str(self.user.id)

        # Try cache first for DCA config
        cache = await get_cache()
        cached_dca = await cache.get_dca_config(
            user_id_str, normalized_pair, signal.tv.timeframe, target_exchange
        )

        if cached_dca:
            logger.debug(f"Using cached DCA config for {signal.tv.symbol} {signal.tv.timeframe}")
            dca_config = DCAGridConfig(**cached_dca)
        else:
            # Fetch from DB and cache
            dca_config_repo = DCAConfigurationRepository(db_session)
            specific_config = await dca_config_repo.get_specific_config(
                user_id=self.user.id,
                pair=normalized_pair,
                timeframe=signal.tv.timeframe,
                exchange=target_exchange
            )

            if specific_config:
                logger.info(f"Using specific DCA configuration for {signal.tv.symbol} {signal.tv.timeframe}")
                # Map DB model to Pydantic Schema
                from enum import Enum as PyEnum

                # Parse pyramid_custom_capitals from DB (convert string keys to Decimal values)
                pyramid_custom_capitals_raw = specific_config.pyramid_custom_capitals or {}
                pyramid_custom_capitals = {
                    k: Decimal(str(v)) for k, v in pyramid_custom_capitals_raw.items()
                }

                dca_config = DCAGridConfig(
                    levels=specific_config.dca_levels,
                    tp_mode=specific_config.tp_mode.value if isinstance(specific_config.tp_mode, PyEnum) else specific_config.tp_mode,
                    tp_aggregate_percent=Decimal(str(specific_config.tp_settings.get("tp_aggregate_percent", 0))),
                    max_pyramids=specific_config.max_pyramids,
                    entry_order_type=specific_config.entry_order_type.value if isinstance(specific_config.entry_order_type, PyEnum) else specific_config.entry_order_type,
                    pyramid_specific_levels=specific_config.pyramid_specific_levels or {},
                    # Capital Override Settings
                    use_custom_capital=specific_config.use_custom_capital or False,
                    custom_capital_usd=Decimal(str(specific_config.custom_capital_usd)) if specific_config.custom_capital_usd else Decimal("200.0"),
                    pyramid_custom_capitals=pyramid_custom_capitals
                )
                # Cache for future requests
                await cache.set_dca_config(
                    user_id_str, normalized_pair, signal.tv.timeframe, target_exchange,
                    dca_config.model_dump(mode='json')
                )
            else:
                logger.error(f"No DCA configuration found for {signal.tv.symbol} {signal.tv.timeframe} (Exchange: {signal.tv.exchange})")
                return f"Configuration Error: No active DCA configuration for {signal.tv.symbol} on {signal.tv.timeframe}."
            
        logger.debug(f"Resolved DCA Config: {dca_config}")

        # Initialize Dependencies
        pg_repo = PositionGroupRepository(db_session)
        exec_pool = ExecutionPoolManager(AsyncSessionLocal, PositionGroupRepository, max_open_groups=risk_config.max_open_positions_global)
        queue_service = QueueManagerService(AsyncSessionLocal, user=self.user, execution_pool_manager=exec_pool)

        # Initialize Exchange Connector (target_exchange already defined above)
        exchange: Optional[Any] = None
        try:
            exchange = ExchangeConfigService.get_connector(self.user, target_exchange)
        except ExchangeConfigError as e:
            logger.error(f"Signal Router: {e}")
            return f"Configuration Error: {e}"
        except Exception as e:
            logger.error(f"Signal Router: Failed to initialize exchange connector for {target_exchange}: {e}")
            return f"Configuration Error: Failed to initialize exchange connector for {signal.tv.exchange}"
        
        try:
            # Precision Validation (configurable via risk_config.precision)
            precision_config = risk_config.precision
            fallback_rules = {
                "tick_size": float(precision_config.fallback_rules.tick_size),
                "step_size": float(precision_config.fallback_rules.step_size),
                "min_qty": float(precision_config.fallback_rules.min_qty),
                "min_notional": float(precision_config.fallback_rules.min_notional),
            }

            try:
                precision_rules = await exchange.get_precision_rules()
                validator = PrecisionValidator(
                    precision_rules=precision_rules,
                    fallback_rules=fallback_rules,
                    block_on_missing=precision_config.block_on_missing_metadata
                )
                if not validator.validate_symbol(signal.tv.symbol):
                    response_message = f"Validation Error: Metadata missing or incomplete for symbol {signal.tv.symbol}"
                    return response_message
            except Exception as e:
                import traceback
                logger.error(f"Signal Router: Precision validation failed: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # If block_on_missing is False, we can proceed with fallback rules
                if not precision_config.block_on_missing_metadata:
                    logger.warning(f"Precision fetch failed but block_on_missing=False. Using fallback rules.")
                    precision_rules = {signal.tv.symbol: fallback_rules}
                    validator = PrecisionValidator(
                        precision_rules=precision_rules,
                        fallback_rules=fallback_rules,
                        block_on_missing=False
                    )
                else:
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

            # --- Handle Exit Signal ---
            intent_type = signal.execution_intent.type.lower() if signal.execution_intent else "signal"
            if intent_type == "exit":
                # For SPOT trading: All positions are "long" (we buy to enter, sell to exit)
                # Exit signals always target the "long" position regardless of action
                target_side = "long"

                # Cancel any queued signals for this symbol/timeframe/side
                # This prevents queued entries from being promoted after the position is closed
                cancelled_count = await queue_service.cancel_queued_signals_on_exit(
                    user_id=self.user.id,
                    symbol=signal.tv.symbol,
                    exchange=signal.tv.exchange.lower(),
                    timeframe=signal.tv.timeframe,
                    side=target_side
                )
                if cancelled_count > 0:
                    logger.info(f"Cancelled {cancelled_count} queued signal(s) for {signal.tv.symbol} on exit")

                # Use SQL-based lookup with row locking and timeframe matching
                group_to_close = await pg_repo.get_active_position_group_for_exit(
                    user_id=self.user.id,
                    symbol=signal.tv.symbol,
                    exchange=signal.tv.exchange.lower(),
                    side=target_side,
                    timeframe=signal.tv.timeframe,  # Match timeframe for exit signals
                    for_update=True
                )
                logger.debug(f"DEBUG: Exit signal - group_to_close: {group_to_close}")

                if group_to_close:
                    await pos_manager.handle_exit_signal(
                        group_to_close.id,
                        max_slippage_percent=risk_config.max_slippage_percent,
                        slippage_action=risk_config.slippage_action,
                        session=db_session  # Pass the existing session to avoid deadlock
                    )
                    await db_session.commit()
                    response_message = f"Exit signal executed for {signal.tv.symbol}"
                    if cancelled_count > 0:
                        response_message += f" ({cancelled_count} queued signal(s) cancelled)"
                else:
                    logger.warning(f"Exit signal received for {signal.tv.symbol} (timeframe: {signal.tv.timeframe}) but no active {target_side} position found.")
                    response_message = f"No active {target_side} position found for {signal.tv.symbol} to exit."
                    if cancelled_count > 0:
                        response_message += f" ({cancelled_count} queued signal(s) cancelled)"

            # --- Handle Entry/Pyramid Signal ---
            else: # intent_type != "exit"
                # For SPOT trading: Only "buy" creates positions (all positions are "long")
                # "sell" action without exit intent is ignored (spot can't short)
                raw_action = signal.tv.action.lower()
                if raw_action == "buy":
                    signal_side = "long"
                elif raw_action == "sell":
                    # In spot trading, a "sell" signal without exit intent is invalid
                    # We can't open short positions in spot markets
                    logger.warning(f"Ignoring sell signal for {signal.tv.symbol} - spot trading does not support short positions. Use execution_intent.type='exit' to close a long position.")
                    return "Signal ignored: Spot trading does not support short positions. Use exit intent to close positions."
                else:
                    signal_side = raw_action # Fallback (assume 'long' if not recognized)

                # Use SQL-based lookup with row locking to prevent race conditions
                existing_group = await pg_repo.get_active_position_group_for_signal(
                    user_id=self.user.id,
                    symbol=signal.tv.symbol,
                    exchange=signal.tv.exchange.lower(),
                    timeframe=signal.tv.timeframe,
                    side=signal_side,
                    for_update=True
                )
                logger.debug(f"DEBUG: Existing group from SQL query: {existing_group}")
                
                # Calculate position size from signal's order_size
                # order_size is the total position size from TradingView
                # position_size_type determines the unit: contracts/base (qty) or quote (USD)
                order_size = Decimal(str(signal.tv.order_size))
                entry_price = Decimal(str(signal.tv.entry_price))
                position_size_type = signal.execution_intent.position_size_type

                # Determine the pyramid index for this signal
                # For new positions: pyramid_index = 0
                # For pyramids: pyramid_index = existing_group.pyramid_count + 1
                if existing_group:
                    pyramid_index = existing_group.pyramid_count + 1
                else:
                    pyramid_index = 0

                # Check if custom capital override is enabled
                if dca_config.use_custom_capital:
                    # Use custom capital from DCA config instead of webhook signal
                    total_capital = dca_config.get_capital_for_pyramid(pyramid_index)
                    logger.info(f"Using custom capital override for pyramid {pyramid_index}: {total_capital} USD")
                else:
                    # Convert order_size to USD value for capital allocation (original behavior)
                    if position_size_type == "quote":
                        # Already in quote currency (e.g., USDT)
                        total_capital = order_size
                    else:
                        # contracts or base: multiply by entry price to get USD value
                        total_capital = order_size * entry_price
                    logger.info(f"Signal order_size: {order_size} ({position_size_type}), Entry: {entry_price}, Total Capital USD: {total_capital}")

                # Apply Risk Config Limit (max exposure) as safety cap
                if risk_config.max_total_exposure_usd:
                    max_exposure = Decimal(str(risk_config.max_total_exposure_usd))
                    if total_capital > max_exposure:
                        logger.warning(f"Order size {total_capital} USD exceeds max exposure {max_exposure} USD. Capping to max exposure.")
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
                    except DuplicatePositionException as e:
                        logger.warning(f"Duplicate position rejected: {e}")
                        return f"Duplicate position rejected: {e}"
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

                # --- Pre-Trade Risk Validation ---
                # Create RiskEngineService and validate before any position execution
                risk_engine = RiskEngineService(
                    session_factory=AsyncSessionLocal,
                    position_group_repository_class=PositionGroupRepository,
                    risk_action_repository_class=RiskActionRepository,
                    dca_order_repository_class=DCAOrderRepository,
                    order_service_class=OrderService,
                    risk_engine_config=risk_config,
                    user=self.user
                )

                # Get all active positions for validation
                active_positions = await pg_repo.get_active_position_groups_for_user(self.user.id)

                # Create a QueuedSignal for validation
                validation_signal = QueuedSignal(
                    user_id=self.user.id,
                    exchange=signal.tv.exchange.lower(),
                    symbol=signal.tv.symbol,
                    timeframe=signal.tv.timeframe,
                    side=signal_side,
                    entry_price=Decimal(str(signal.tv.entry_price)),
                    signal_payload=signal.model_dump(mode='json')
                )

                # Perform pre-trade risk validation
                is_pyramid_continuation = existing_group is not None
                is_allowed, rejection_reason = await risk_engine.validate_pre_trade_risk(
                    signal=validation_signal,
                    active_positions=active_positions,
                    allocated_capital_usd=total_capital,
                    session=db_session,
                    is_pyramid_continuation=is_pyramid_continuation
                )

                if not is_allowed:
                    logger.warning(f"Pre-trade risk validation failed for {signal.tv.symbol}: {rejection_reason}")
                    return f"Risk validation failed: {rejection_reason}"

                if existing_group:
                    # Pyramid Logic Check
                    # pyramid_count starts at 0 for initial entry
                    # max_pyramids is the maximum pyramid_count value allowed
                    if existing_group.pyramid_count < dca_config.max_pyramids:
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
                        logger.warning(f"Max pyramids reached for {signal.tv.symbol} (pyramid_count: {existing_group.pyramid_count}, max: {dca_config.max_pyramids}). Signal ignored.")
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
