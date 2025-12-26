import json
import uuid
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.user import User
from app.models.position_group import PositionGroup
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.repositories.dca_configuration import DCAConfigurationRepository
from app.services.execution_pool_manager import ExecutionPoolManager
from app.schemas.webhook_payloads import WebhookPayload
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.services.position_manager import PositionManagerService
from app.services.order_management import OrderService
from app.services.grid_calculator import GridCalculatorService
from app.services.queue_priority import calculate_queue_priority, explain_priority
from app.schemas.grid_config import PriorityRulesConfig

logger = logging.getLogger(__name__)



class QueueManagerService:
    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        user: Optional[User] = None, # Context user for add/remove operations
        queued_signal_repository_class=QueuedSignalRepository,
        position_group_repository_class=PositionGroupRepository,
        exchange_connector=None,
        execution_pool_manager: Optional[ExecutionPoolManager] = None,
        # Dependencies for promotion execution (optional/stub for now)
        position_manager_service=None,
        polling_interval_seconds=10
    ):
        self.session_factory = session_factory
        self.user = user
        self.queued_signal_repository_class = queued_signal_repository_class
        self.position_group_repository_class = position_group_repository_class
        self.exchange_connector = exchange_connector
        self.execution_pool_manager = execution_pool_manager
        self.position_manager_service = position_manager_service
        
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._promotion_task = None
        self._encryption_service = EncryptionService()

    async def add_signal_to_queue(self, payload: WebhookPayload) -> QueuedSignal:
        """
        Adds a new signal to the queue or updates an existing one (replacement).
        """
        if not self.user:
            logger.error("User context required to add signal to queue, but self.user is None.")
            raise ValueError("User context required to add signal to queue.")

        logger.debug(f"Attempting to add/update signal for user {self.user.id} symbol {payload.tv.symbol}.")

        async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            
            # Check for existing signal
            existing_signal = await repo.get_by_symbol_timeframe_side(
                symbol=payload.tv.symbol,
                timeframe=payload.tv.timeframe,
                side=payload.tv.action, # Assuming action maps to side
                exchange=payload.tv.exchange.lower()
            )
            
            if existing_signal:
                logger.debug(f"Existing signal found for {existing_signal.symbol}. Applying replacement logic.")
                # Replacement Logic
                existing_signal.entry_price = Decimal(str(payload.tv.entry_price))
                existing_signal.replacement_count += 1
                # Keep original queued_at to respect FIFO tiebreak based on first intent
                existing_signal.signal_payload = payload.model_dump(mode='json')
                
                await repo.update(existing_signal)
                await session.commit()
                logger.info(f"Replaced queued signal for {existing_signal.symbol}, count: {existing_signal.replacement_count}")
                return existing_signal
            else:
                logger.debug(f"No existing signal found for {payload.tv.symbol}. Creating new signal.")
                # New Signal
                new_signal = QueuedSignal(
                    user_id=self.user.id,
                    exchange=payload.tv.exchange.lower(),
                    symbol=payload.tv.symbol,
                    timeframe=payload.tv.timeframe,
                    side=payload.tv.action,
                    entry_price=Decimal(str(payload.tv.entry_price)),
                    signal_payload=payload.model_dump(mode='json'),
                    status=QueueStatus.QUEUED
                )
                await repo.create(new_signal)
                await session.commit()
                logger.info(f"Added new signal to queue: {new_signal.symbol}")
                return new_signal

    async def remove_from_queue(self, signal_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> bool:
        async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            signal = await repo.get_by_id(signal_id)
            if not signal:
                return False

            if user_id and signal.user_id != user_id:
                logger.warning(f"User {user_id} attempted to remove signal {signal_id} belonging to {signal.user_id}")
                return False

            result = await repo.delete(signal_id)
            if result:
                await session.commit()
            return result

    async def cancel_queued_signals_on_exit(
        self,
        user_id: uuid.UUID,
        symbol: str,
        exchange: str,
        timeframe: int,
        side: str
    ) -> int:
        """
        Cancel all queued signals for a symbol/timeframe/side when an exit signal arrives.

        This ensures that pending entry signals don't get promoted after the position
        has already been closed by an exit signal.

        Args:
            user_id: The user's ID
            symbol: Trading symbol (e.g., "BTCUSDT")
            exchange: Exchange name (e.g., "binance")
            timeframe: Timeframe in minutes
            side: Position side ("long" or "short")

        Returns:
            Number of queued signals cancelled
        """
        async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            cancelled_count = await repo.cancel_queued_signals_for_symbol(
                user_id=str(user_id),
                symbol=symbol,
                exchange=exchange.lower(),
                timeframe=timeframe,
                side=side
            )
            if cancelled_count > 0:
                await session.commit()
                logger.info(
                    f"Cancelled {cancelled_count} queued signal(s) for {symbol} {timeframe}m {side} "
                    f"on exit signal (user: {user_id})"
                )
            return cancelled_count

    async def get_all_queued_signals(self, user_id: Optional[uuid.UUID] = None) -> List[QueuedSignal]:
         async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            if user_id:
                signals = await repo.get_all_queued_signals_for_user(user_id)
            else:
                signals = await repo.get_all_queued_signals()

            # Dynamic Priority Calculation
            if signals and user_id:
                # We need user context to calculate priority (rules + active positions)
                # If user_id is provided, we can do it efficiently.
                # If not (admin view), we might need to do it per-user or just show raw queue.
                # For now, assuming this is primarily consumed by the specific user.
                
                user = await session.get(User, user_id)
                if user:
                    # Load Config
                    try:
                        risk_config = RiskEngineConfig(**user.risk_config)
                        priority_config = risk_config.priority_rules
                    except Exception:
                        from app.schemas.grid_config import PriorityRulesConfig
                        priority_config = PriorityRulesConfig()

                    # Load Active Groups (for Pyramid check)
                    pos_group_repo = self.position_group_repository_class(session)
                    active_groups = await pos_group_repo.get_active_position_groups_for_user(user_id)

                    # Calculate and attach dynamic fields
                    for signal in signals:
                        signal.priority_score = calculate_queue_priority(signal, active_groups, priority_config)
                        signal.priority_explanation = explain_priority(signal, active_groups, priority_config)
            
            # Sort by priority score desc for display
            signals.sort(key=lambda s: s.priority_score if hasattr(s, 'priority_score') else Decimal(0), reverse=True)
            
            return signals

    async def get_queue_history(self, user_id: Optional[uuid.UUID] = None, limit: int = 50) -> List[QueuedSignal]:
        async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            if user_id:
                return await repo.get_history_for_user(user_id, limit)
            return await repo.get_history(limit)

    async def force_add_specific_signal_to_pool(self, signal_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[QueuedSignal]:
        # This method effectively "Promotes" it but bypasses checks?
        # Or just changes status and lets execution happen?
        # For now, implementing as a force-promote.
         async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            signal = await repo.get_by_id(signal_id)
            if signal:
                if user_id and signal.user_id != user_id:
                    logger.warning(f"User {user_id} attempted to force promote signal {signal_id} belonging to {signal.user_id}")
                    return None

                signal.status = QueueStatus.PROMOTED
                signal.promoted_at = datetime.utcnow()
                await repo.update(signal)
                await session.commit()
                return signal
            return None
    
    async def promote_specific_signal(self, signal_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[QueuedSignal]:
         async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            signal = await repo.get_by_id(signal_id)
            if not signal:
                return None
            
            if user_id and signal.user_id != user_id:
                logger.warning(f"User {user_id} attempted to promote signal {signal_id} belonging to {signal.user_id}")
                return None
            
            # Check slot
            if self.execution_pool_manager:
                user = await session.get(User, signal.user_id)
                if not user:
                    logger.error(f"User {signal.user_id} not found for signal {signal.id}")
                    return None

                try:
                    # Ensure config is loaded from JSON string if coming from DB
                    risk_config_data = user.risk_config
                    if isinstance(risk_config_data, str):
                        risk_config_data = json.loads(risk_config_data)
                    risk_config = RiskEngineConfig(**risk_config_data)
                    
                    user_max_groups = risk_config.max_open_positions_global
                except Exception as e:
                    logger.error(f"Failed to load user config for user {user.id}: {e}")
                    # Fallback to global default if user config is invalid
                    user_max_groups = None

                # Load Priority Config to check if Pyramiding allows bypass
                priority_config = risk_config.priority_rules
                pyramid_rule_enabled = priority_config.priority_rules_enabled.get("same_pair_timeframe", False)

                pos_group_repo = self.position_group_repository_class(session)
                active_groups = await pos_group_repo.get_active_position_groups_for_user(signal.user_id)
                is_pyramid = any(
                    g.symbol == signal.symbol and 
                    g.exchange == signal.exchange and
                    g.timeframe == signal.timeframe and 
                    g.side == signal.side
                    for g in active_groups
                )
                
                # Only treat as pyramid (bypass max groups) if the rule is ENABLED
                if is_pyramid and pyramid_rule_enabled:
                    logger.info(f"Signal {signal.symbol} matches active group and 'same_pair_timeframe' rule is ENABLED. Bypassing pool limit for pyramid.")
                    # Pyramid with bypass enabled - skip slot check entirely
                    slot_granted = True
                else:
                    if is_pyramid and not pyramid_rule_enabled:
                        logger.info(f"Signal {signal.symbol} matches active group, but 'same_pair_timeframe' rule is DISABLED. Competing for slot.")
                    slot_granted = await self.execution_pool_manager.request_slot(
                        max_open_groups_override=user_max_groups
                    )

                if not slot_granted:
                    return None
            
            # Snap-shot the priority metrics for history
            priority_config = PriorityRulesConfig(**user.risk_config.get("priority_rules", {}))
            
            signal.priority_score = calculate_queue_priority(signal, active_groups, priority_config)
            signal.priority_explanation = explain_priority(signal, active_groups, priority_config)

            signal.status = QueueStatus.PROMOTED
            signal.promoted_at = datetime.utcnow()
            await repo.update(signal)
            await session.commit()
            return signal

    async def promote_highest_priority_signal(self, session: AsyncSession):
        """
        Scans the queue, updates priorities, and attempts to promote the best signal.
        """
        queue_repo = self.queued_signal_repository_class(session)
        pos_group_repo = self.position_group_repository_class(session)
            
        queued_signals = await queue_repo.get_all_queued_signals(for_update=False)
        if not queued_signals:
            return

        # Group by user
        signals_by_user: Dict[uuid.UUID, List[QueuedSignal]] = {}
        for s in queued_signals:
            if s.user_id not in signals_by_user:
                signals_by_user[s.user_id] = []
            signals_by_user[s.user_id].append(s)

        for user_id, user_signals in signals_by_user.items():
            user = await session.get(User, user_id)
            if not user:
                logger.debug(f"User {user_id} not found in session, skipping signals.")
                continue

            active_groups = await pos_group_repo.get_active_position_groups_for_user(user_id)
            logger.debug(f"Processing {len(user_signals)} signals for user {user.username}. Active groups: {len(active_groups)}")

            # Group signals by exchange for efficient price fetching
            signals_by_exchange = {}
            for s in user_signals:
                if s.exchange not in signals_by_exchange:
                    signals_by_exchange[s.exchange] = []
                signals_by_exchange[s.exchange].append(s)

            # Update prices for each exchange group
            for ex_name, signals in signals_by_exchange.items():
                try:
                    # Initialize Exchange
                    exchange = None
                    if self.exchange_connector:
                         exchange = self.exchange_connector
                    else:
                         # Multi-key lookup
                         encrypted_data = user.encrypted_api_keys
                         target_data = None
                         if isinstance(encrypted_data, dict):
                             if ex_name in encrypted_data:
                                 target_data = encrypted_data[ex_name]
                             elif "encrypted_data" not in encrypted_data:
                                 # No keys for this exchange
                                 pass
                         
                         if target_data:
                             # Extract settings from stored config
                             testnet = target_data.get("testnet", False) if isinstance(target_data, dict) else False
                             account_type = target_data.get("account_type", "UNIFIED") if isinstance(target_data, dict) else "UNIFIED"
                             default_type = target_data.get("default_type", "spot") if isinstance(target_data, dict) else "spot"
                             
                             exchange_config = {
                                 "encrypted_data": target_data if not isinstance(target_data, dict) else target_data.get("encrypted_data", target_data),
                                 "testnet": testnet,
                                 "account_type": account_type,
                                 "default_type": default_type
                             }
                             exchange = get_exchange_connector(ex_name, exchange_config)

                    if exchange:
                        for signal in signals:
                            try:
                                current_price = await exchange.get_current_price(signal.symbol)
                                current_price_dec = Decimal(str(current_price))
                                if signal.side == "long":
                                    pnl_pct = (current_price_dec - signal.entry_price) / signal.entry_price * Decimal("100")
                                else:
                                    pnl_pct = (signal.entry_price - current_price_dec) / signal.entry_price * Decimal("100")
                                
                                signal.current_loss_percent = pnl_pct
                                await queue_repo.update(signal)
                            except Exception as e:
                                logger.warning(f"Failed to update price for {signal.symbol}: {e}")
                                pass
                except Exception as e:
                    logger.error(f"Failed to process signals for exchange {ex_name}: {e}")

            # Commit updates to signal priorities/loss percent
            await session.commit()
            
            # Load user's priority configuration
            try:
                risk_config = RiskEngineConfig(**user.risk_config)
                priority_config = risk_config.priority_rules
            except Exception as e:
                logger.error(f"Failed to load priority config for user {user.id}: {e}")
                from app.schemas.grid_config import PriorityRulesConfig
                priority_config = PriorityRulesConfig()  # Use default
            
            # Log active priority rules
            enabled_rules = [r for r, enabled in priority_config.priority_rules_enabled.items() if enabled]
            logger.info(f"Queue processing for user {user.username}")
            logger.info(f"Active priority rules: {enabled_rules}")
            logger.info(f"Rule execution order: {priority_config.priority_order}")

            # Calculate Priorities with configuration
            sorted_signals = sorted(
                user_signals,
                key=lambda s: calculate_queue_priority(s, active_groups, priority_config),
                reverse=True
            )
            
            # Log top candidates with priority explanations
            for idx, signal in enumerate(sorted_signals[:3]):  # Log top 3
                priority_explanation = explain_priority(signal, active_groups, priority_config)
                logger.info(f"  #{idx+1} candidate: {priority_explanation}")

            if not sorted_signals:
                continue

            best_signal = sorted_signals[0]
            
            # Attempt Promotion
            if not self.execution_pool_manager:
                continue

            # Load Risk Config from User
            try:
                # Ensure configs are loaded from JSON strings if coming from DB
                risk_config_data = user.risk_config
                if isinstance(risk_config_data, str):
                    risk_config_data = json.loads(risk_config_data)
                risk_config = RiskEngineConfig(**risk_config_data)
            except Exception as e:
                logger.error(f"Failed to load user risk config: {e}")
                continue

            # Load DCA Config for the specific signal
            try:
                dca_config_repo = DCAConfigurationRepository(session)

                # Normalize the pair format for lookup
                normalized_pair = best_signal.symbol
                if '/' not in normalized_pair:
                    if normalized_pair.endswith('USDT'):
                        normalized_pair = normalized_pair[:-4] + '/' + normalized_pair[-4:]
                    elif normalized_pair.endswith(('USD', 'BTC', 'ETH', 'BNB')):
                        normalized_pair = normalized_pair[:-3] + '/' + normalized_pair[-3:]

                specific_config = await dca_config_repo.get_specific_config(
                    user_id=user.id,
                    pair=normalized_pair,
                    timeframe=best_signal.timeframe,
                    exchange=best_signal.exchange.lower()
                )

                if specific_config:
                    logger.info(f"Using specific DCA configuration for {best_signal.symbol} {best_signal.timeframe}")
                    # Map DB model to Pydantic Schema
                    from enum import Enum as PyEnum
                    dca_config = DCAGridConfig(
                        levels=specific_config.dca_levels,
                        tp_mode=specific_config.tp_mode.value if isinstance(specific_config.tp_mode, PyEnum) else specific_config.tp_mode,
                        tp_aggregate_percent=Decimal(str(specific_config.tp_settings.get("tp_aggregate_percent", 0))),
                        max_pyramids=specific_config.max_pyramids,
                        entry_order_type=specific_config.entry_order_type.value if isinstance(specific_config.entry_order_type, PyEnum) else specific_config.entry_order_type,
                        pyramid_specific_levels=specific_config.pyramid_specific_levels or {}
                    )
                else:
                    logger.error(f"No DCA configuration found for {best_signal.symbol} {best_signal.timeframe} (Exchange: {best_signal.exchange})")
                    continue
            except Exception as e:
                logger.error(f"Failed to load DCA config for signal {best_signal.symbol}: {e}")
                continue

            is_pyramid = any(
                g.symbol == best_signal.symbol and
                g.exchange == best_signal.exchange and
                g.timeframe == best_signal.timeframe and
                g.side == best_signal.side
                for g in active_groups
            )

            # Retrieve already loaded config (or default)
            pyramid_rule_enabled = priority_config.priority_rules_enabled.get("same_pair_timeframe", False)

            # Only treat as pyramid (bypass max groups) if the rule is ENABLED
            user_max_groups = risk_config.max_open_positions_global
            if is_pyramid and pyramid_rule_enabled:
                logger.info(f"Signal {best_signal.symbol} matches active group and 'same_pair_timeframe' rule is ENABLED. Bypassing pool limit for pyramid.")
                slot_granted = True
            else:
                if is_pyramid and not pyramid_rule_enabled:
                    logger.info(f"Signal {best_signal.symbol} matches active group, but 'same_pair_timeframe' rule is DISABLED. Competing for slot.")
                slot_granted = await self.execution_pool_manager.request_slot(
                    max_open_groups_override=user_max_groups
                )
            
            if slot_granted:
                # Ensure priority metrics are saved to history
                best_signal.priority_score = calculate_queue_priority(best_signal, active_groups, priority_config)
                best_signal.priority_explanation = explain_priority(best_signal, active_groups, priority_config)
                
                logger.info(f"Slot granted. Promoting signal: {best_signal.priority_explanation}")
                best_signal.status = QueueStatus.PROMOTED
                best_signal.promoted_at = datetime.utcnow()
                await queue_repo.update(best_signal)
                await session.commit() 
                
                try:
                    # Instantiate PositionManager locally
                    grid_calc = GridCalculatorService()
                    pos_manager = PositionManagerService(
                        session_factory=self.session_factory,
                        user=user,
                        position_group_repository_class=self.position_group_repository_class,
                        grid_calculator_service=grid_calc,
                        order_service_class=OrderService
                    )
                    
                    # Fetch capital using correct connector
                    total_capital = Decimal("1000") # Default fallback
                    try:
                        # Re-init connector for best_signal.exchange to get balance
                        exchange = None
                        if self.exchange_connector:
                            exchange = self.exchange_connector
                        else:
                                encrypted_data = user.encrypted_api_keys
                                target_data = None
                                if isinstance(encrypted_data, dict) and best_signal.exchange.lower() in encrypted_data:
                                    target_data = encrypted_data[best_signal.exchange.lower()]
                                
                                if target_data:
                                    # Extract settings from stored config
                                    testnet = target_data.get("testnet", False) if isinstance(target_data, dict) else False
                                    account_type = target_data.get("account_type", "UNIFIED") if isinstance(target_data, dict) else "UNIFIED"
                                    default_type = target_data.get("default_type", "spot") if isinstance(target_data, dict) else "spot"
                                    
                                    exchange_config = {
                                        "encrypted_data": target_data if not isinstance(target_data, dict) else target_data.get("encrypted_data", target_data),
                                        "testnet": testnet,
                                        "account_type": account_type,
                                        "default_type": default_type
                                    }
                                    exchange = get_exchange_connector(best_signal.exchange.lower(), exchange_config)

                        if exchange:
                            balance = await exchange.fetch_balance()
                            # Standardized flat structure (e.g., {'USDT': 1000.0})
                            if "total" in balance and isinstance(balance["total"], dict):
                                balance = balance["total"]
                            
                            if isinstance(balance, dict):
                                total_capital = Decimal(str(balance.get('USDT', 1000)))
                            await exchange.close()
                    except Exception as e:
                        logger.warning(f"Failed to fetch balance for user {user.id}: {e}")
                        pass

                    # --- POSITION SIZING LOGIC ---
                    # 1. Calculate based on percentage
                    alloc_percent = risk_config.risk_per_position_percent if risk_config.risk_per_position_percent else Decimal("10.0")
                    allocated_capital = total_capital * (alloc_percent / Decimal("100"))
                    
                    # 2. Cap by absolute amount if configured
                    if risk_config.risk_per_position_cap_usd and risk_config.risk_per_position_cap_usd > 0:
                        if allocated_capital > risk_config.risk_per_position_cap_usd:
                            allocated_capital = risk_config.risk_per_position_cap_usd

                    # 3. Cap total exposure (Global Safety)
                    if risk_config.max_total_exposure_usd and risk_config.max_total_exposure_usd > 0:
                        if allocated_capital > risk_config.max_total_exposure_usd:
                            allocated_capital = risk_config.max_total_exposure_usd

                    logger.info(f"Capital Allocation: Total {total_capital} USD, Allocating {allocated_capital} USD ({alloc_percent}%)")

                    # RE-EVALUATE PYRAMID STATUS ON EXECUTION
                    # Even if is_pyramid was False (due to disabled rule), we check again here
                    # because now that we have a slot, if it matches an active group, we MUST pyramid.
                    target_group = next((g for g in active_groups if g.symbol == best_signal.symbol and g.exchange == best_signal.exchange and g.timeframe == best_signal.timeframe and g.side == best_signal.side), None)

                    # pyramid_count starts at 0 for initial entry
                    # max_pyramids is the maximum pyramid_count value allowed
                    if target_group and target_group.pyramid_count < dca_config.max_pyramids:
                         logger.info(f"Signal {best_signal.symbol} matches active group {target_group.id}. Executing as Pyramid.")
                         await pos_manager.handle_pyramid_continuation(
                                session=session,
                                user_id=user.id,
                                signal=best_signal,
                                existing_position_group=target_group,
                                risk_config=risk_config,
                                dca_grid_config=dca_config,
                                total_capital_usd=allocated_capital
                            )
                    else:
                        if target_group:
                             logger.info(f"Signal {best_signal.symbol} matches active group {target_group.id} but max pyramids reached. Executing as NEW Position if allowed (or will fail/warn).")

                        await pos_manager.create_position_group_from_signal(
                            session=session,
                            user_id=user.id,
                            signal=best_signal,
                            risk_config=risk_config,
                            dca_grid_config=dca_config,
                            total_capital_usd=allocated_capital
                        )
                    
                    await session.commit()

                except Exception as e:
                    logger.error(f"Execution failed for promoted signal {best_signal.id}: {e}")
                    pass
            else:
                logger.debug(f"No slot granted for signal {best_signal.symbol}.")

    async def start_promotion_task(self):
        self._running = True
        self._promotion_task = asyncio.create_task(self._promotion_loop())
        logger.info("Queue Promotion Task Started")

    async def stop_promotion_task(self):
        self._running = False
        if self._promotion_task:
            self._promotion_task.cancel()
            try:
                await self._promotion_task
            except asyncio.CancelledError:
                pass
        logger.info("Queue Promotion Task Stopped")

    async def _promotion_loop(self):
        cycle_count = 0
        error_count = 0
        last_error = None
        promotions_count = 0

        while self._running:
            try:
                async with self.session_factory() as session:
                    result = await self.promote_highest_priority_signal(session)
                    await session.commit()
                    if result:
                        promotions_count += 1

                cycle_count += 1

                # Report health metrics
                await self._report_health(
                    status="running",
                    metrics={
                        "cycle_count": cycle_count,
                        "promotions_count": promotions_count,
                        "error_count": error_count,
                        "last_error": last_error
                    }
                )
            except Exception as e:
                error_count += 1
                last_error = str(e)
                logger.error(f"Error in promotion loop: {e}")

                await self._report_health(
                    status="error",
                    metrics={
                        "cycle_count": cycle_count,
                        "promotions_count": promotions_count,
                        "error_count": error_count,
                        "last_error": last_error
                    }
                )

            await asyncio.sleep(self.polling_interval_seconds)

    async def _report_health(self, status: str, metrics: dict = None):
        """Report service health to cache."""
        try:
            from app.core.cache import get_cache
            cache = await get_cache()
            await cache.update_service_health("queue_manager", status, metrics)
        except Exception as e:
            logger.debug(f"Failed to report health: {e}")
