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
from app.services.execution_pool_manager import ExecutionPoolManager
from app.schemas.webhook_payloads import WebhookPayload
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

logger = logging.getLogger(__name__)

def calculate_queue_priority(signal: QueuedSignal, active_groups: List[PositionGroup]) -> Decimal:
    score = Decimal("0.0")

    # Calculate sub-components that can be used across tiers for tie-breaking
    time_in_queue_score = Decimal("0.0")
    if signal.queued_at:
        time_in_queue = (datetime.utcnow() - signal.queued_at).total_seconds()
        time_in_queue_score = Decimal(time_in_queue) * Decimal("0.001")

    replacement_count_score = Decimal(signal.replacement_count) * Decimal("100.0")

    loss_percent_score = Decimal("0.0")
    if signal.current_loss_percent is not None and signal.current_loss_percent < Decimal("0"):
        loss_percent_score = abs(signal.current_loss_percent) * Decimal("10000.0") # Multiplier chosen to ensure its range is above replacement/FIFO, but below pyramid

    # Apply tiers strictly
    # 1. Pyramid Continuation (Highest Priority)
    is_pyramid = any(
        g.symbol == signal.symbol and
        g.timeframe == signal.timeframe and
        g.side == signal.side and
        g.user_id == signal.user_id
        for g in active_groups
    )
    if is_pyramid:
        # Base + tie-breakers for pyramid continuation
        return Decimal("10000000.0") + loss_percent_score + replacement_count_score + time_in_queue_score

    # 2. Deepest Current Loss Percentage
    # Base + tie-breakers (replacement, FIFO) for deepest loss
    if signal.current_loss_percent is not None and signal.current_loss_percent < Decimal("0"):
        return Decimal("1000000.0") + loss_percent_score + replacement_count_score + time_in_queue_score

    # 3. Highest Replacement Count
    # Base + tie-breaker (FIFO) for replacement count
    if signal.replacement_count > 0:
        return Decimal("10000.0") + replacement_count_score + time_in_queue_score

    # 4. FIFO (Lowest Priority)
    return Decimal("1000.0") + time_in_queue_score

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
                side=payload.tv.action # Assuming action maps to side
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
                    exchange=payload.tv.exchange,
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

    async def get_all_queued_signals(self, user_id: Optional[uuid.UUID] = None) -> List[QueuedSignal]:
         async with self.session_factory() as session:
            repo = self.queued_signal_repository_class(session)
            if user_id:
                return await repo.get_all_queued_signals_for_user(user_id)
            return await repo.get_all_queued_signals()

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
                # We assume no pyramid check for manual promotion, or we check it?
                # Let's check simply.
                pos_group_repo = self.position_group_repository_class(session)
                active_groups = await pos_group_repo.get_active_position_groups_for_user(signal.user_id)
                is_pyramid = any(
                    g.symbol == signal.symbol and 
                    g.timeframe == signal.timeframe and 
                    g.side == signal.side
                    for g in active_groups
                )
                
                slot_granted = await self.execution_pool_manager.request_slot(is_pyramid_continuation=is_pyramid)
                if not slot_granted:
                    return None
            
            signal.status = QueueStatus.PROMOTED
            signal.promoted_at = datetime.utcnow()
            await repo.update(signal)
            await session.commit()
            return signal

    async def promote_highest_priority_signal(self):
        """
        Scans the queue, updates priorities, and attempts to promote the best signal.
        """
        async with self.session_factory() as session:
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

                # Initialize Exchange
                try:
                    api_key, api_secret = self._encryption_service.decrypt_keys(user.encrypted_api_keys)
                    if self.exchange_connector: # Use provided connector if available (for tests)
                        exchange = self.exchange_connector
                        logger.debug(f"Using mocked exchange connector for user {user.username}.")
                    else: # Otherwise, get a new one (for production)
                        exchange = get_exchange_connector(user.exchange, api_key=api_key, secret_key=api_secret)
                        logger.debug(f"Initialized new exchange connector ({user.exchange}) for user {user.username}.")
                except Exception as e:
                    logger.error(f"Failed to init exchange for user {user_id}: {e}")
                    continue
                
                # Update Current Loss Percent
                for signal in user_signals:
                    logger.debug(f"Attempting to get current price for signal {signal.symbol} (ID: {signal.id}).")
                    try:
                        current_price = await exchange.get_current_price(signal.symbol) # THIS IS THE CALL BEING MISSED
                        logger.debug(f"Fetched price for {signal.symbol}: {current_price}. Entry: {signal.entry_price}")
                        if signal.side == "long":
                            pnl_pct = (current_price - signal.entry_price) / signal.entry_price * 100
                        else:
                            pnl_pct = (signal.entry_price - current_price) / signal.entry_price * 100
                        
                        signal.current_loss_percent = pnl_pct
                        await queue_repo.update(signal)
                        logger.debug(f"Updated loss percent for {signal.symbol}: {pnl_pct}%")
                    except Exception as e:
                        logger.warning(f"Failed to fetch price or update loss percent for {signal.symbol} (ID: {signal.id}): {e}")
                        pass
                
                # Commit updates to signal priorities/loss percent
                await session.commit()

                # Calculate Priorities
                sorted_signals = sorted(
                    user_signals,
                    key=lambda s: calculate_queue_priority(s, active_groups),
                    reverse=True
                )

                if not sorted_signals:
                    logger.debug(f"No sorted signals for user {user.username} after priority calculation.")
                    continue

                best_signal = sorted_signals[0]
                logger.debug(f"Best signal for user {user.username}: {best_signal.symbol} (Score: {best_signal.priority_score}).")
                
                # Attempt Promotion
                if not self.execution_pool_manager:
                    logger.warning("Execution Pool Manager not available.")
                    continue

                is_pyramid = any(
                    g.symbol == best_signal.symbol and 
                    g.timeframe == best_signal.timeframe and 
                    g.side == best_signal.side
                    for g in active_groups
                )

                logger.debug(f"Requesting slot for {best_signal.symbol}. Is pyramid: {is_pyramid}")
                slot_granted = await self.execution_pool_manager.request_slot(is_pyramid_continuation=is_pyramid)
                
                if slot_granted:
                    logger.info(f"Promoting signal {best_signal.symbol} (Score: {best_signal.priority_score})")
                    best_signal.status = QueueStatus.PROMOTED
                    best_signal.promoted_at = datetime.utcnow()
                    await queue_repo.update(best_signal)
                    await session.commit() # Commit promotion status update
                    logger.debug(f"Signal {best_signal.id} status updated to PROMOTED.")
                    
                    if self.position_manager_service:
                        try:
                            # Load Configs from User
                            risk_config = RiskEngineConfig(**user.risk_config)
                            dca_config = DCAGridConfig.model_validate(user.dca_grid_config)
                            
                            total_capital = Decimal("1000") # Default
                            if exchange:
                                try:
                                    balance = await exchange.fetch_balance()
                                    if isinstance(balance, dict) and 'total' in balance:
                                        total_capital = Decimal(str(balance['total'].get('USDT', 1000)))
                                except Exception:
                                    pass

                            if is_pyramid:
                                existing_group = next((g for g in active_groups if g.symbol == best_signal.symbol and g.timeframe == best_signal.timeframe and g.side == best_signal.side), None)
                                if existing_group:
                                    await self.position_manager_service.handle_pyramid_continuation(
                                        session=session,
                                        user_id=user.id,
                                        signal=best_signal,
                                        existing_position_group=existing_group,
                                        risk_config=risk_config,
                                        dca_grid_config=dca_config,
                                        total_capital_usd=total_capital
                                    )
                            else:
                                await self.position_manager_service.create_position_group_from_signal(
                                    session=session,
                                    user_id=user.id,
                                    signal=best_signal,
                                    risk_config=risk_config,
                                    dca_grid_config=dca_config,
                                    total_capital_usd=total_capital
                                )
                            
                            # We should commit after PositionManagerService operations if they modified DB
                            # PositionManagerService takes `session`, so it participates in this transaction.
                            await session.commit()

                        except Exception as e:
                            logger.error(f"Execution failed for promoted signal {best_signal.id}: {e}")
                            # Ideally rollback here if we want atomic promotion+execution
                            # But session usage is tricky if partial commits happened.
                            pass
                else:
                    logger.info(f"No slot granted for signal {best_signal.symbol}.")

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
        while self._running:
            try:
                await self.promote_highest_priority_signal()
            except Exception as e:
                logger.error(f"Error in promotion loop: {e}")
            
            await asyncio.sleep(self.polling_interval_seconds)
