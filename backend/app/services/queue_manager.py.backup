"""
Service for managing the execution pool and the signal queue.
"""
import asyncio
import logging
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.position_manager import PositionManagerService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig

logger = logging.getLogger(__name__)

def find_active_group(active_groups: List[PositionGroup], symbol: str, timeframe: int) -> Optional[PositionGroup]:
    for group in active_groups:
        if group.symbol == symbol and group.timeframe == timeframe:
            return group
    return None

def calculate_queue_priority(signal: QueuedSignal, active_groups: List[PositionGroup]) -> float:
    existing_group = find_active_group(active_groups, signal.symbol, signal.timeframe)
    if existing_group:
        time_in_queue = (datetime.utcnow() - signal.queued_at).total_seconds()
        return 1_000_000 + (10_000 - time_in_queue)
    if signal.current_loss_percent is not None:
        loss_score = abs(signal.current_loss_percent) * 1000
        return 100_000 + float(loss_score)
    if signal.replacement_count > 0:
        return 10_000 + (signal.replacement_count * 100)
    time_in_queue = (datetime.utcnow() - signal.queued_at).total_seconds()
    fifo_score = min(time_in_queue, 9999) 
    return 1_000 + fifo_score

class QueueManagerService:
    def __init__(
        self,
        session_factory: callable,
        queued_signal_repository_class: type[QueuedSignalRepository],
        position_group_repository_class: type[PositionGroupRepository],
        exchange_connector: ExchangeInterface,
        execution_pool_manager: ExecutionPoolManager,
        position_manager_service: PositionManagerService,
        risk_engine_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal,
        polling_interval_seconds: int = 5
    ):
        self.session_factory = session_factory
        self.queued_signal_repository_class = queued_signal_repository_class
        self.position_group_repository_class = position_group_repository_class
        self.exchange_connector = exchange_connector
        self.execution_pool_manager = execution_pool_manager
        self.position_manager_service = position_manager_service
        self.risk_engine_config = risk_engine_config
        self.dca_grid_config = dca_grid_config
        self.total_capital_usd = total_capital_usd
        self.polling_interval_seconds = polling_interval_seconds
        self._running = False
        self._promotion_task = None

    async def add_to_queue(self, signal_payload: dict) -> QueuedSignal:
        async for session in self.session_factory():
            queued_signal_repo = self.queued_signal_repository_class(session)
            existing_signal = await queued_signal_repo.get_by_symbol_timeframe_side(
                signal_payload["symbol"], 
                signal_payload["timeframe"], 
                signal_payload["side"]
            )
            if existing_signal:
                existing_signal.replacement_count += 1
                existing_signal.entry_price = Decimal(str(signal_payload["entry_price"]))
                existing_signal.signal_payload = signal_payload
                existing_signal.queued_at = datetime.utcnow()
                await queued_signal_repo.update(existing_signal.id, {
                    "replacement_count": existing_signal.replacement_count,
                    "entry_price": existing_signal.entry_price,
                    "signal_payload": existing_signal.signal_payload,
                    "queued_at": existing_signal.queued_at
                })
                logger.info(f"Replaced queued signal {existing_signal.id}. New replacement count: {existing_signal.replacement_count}")
                return existing_signal
            else:
                new_signal = QueuedSignal(
                    user_id=uuid.UUID(signal_payload["user_id"]),
                    exchange=signal_payload["exchange"],
                    symbol=signal_payload["symbol"],
                    timeframe=signal_payload["timeframe"],
                    side=signal_payload["side"],
                    entry_price=Decimal(str(signal_payload["entry_price"])),
                    signal_payload=signal_payload,
                    status=QueueStatus.QUEUED,
                    queued_at=datetime.utcnow()
                )
                await queued_signal_repo.create(new_signal)
                logger.info(f"Added new signal {new_signal.id} to queue for {new_signal.symbol}")
                return new_signal

    async def remove_from_queue(self, signal_id: uuid.UUID) -> bool:
        async for session in self.session_factory():
            queued_signal_repo = self.queued_signal_repository_class(session)
            signal = await queued_signal_repo.get_by_id(signal_id)
            if signal:
                await queued_signal_repo.delete(signal_id)
                logger.info(f"Removed signal {signal_id} from queue.")
                return True
            logger.warning(f"Signal {signal_id} not found in queue for removal.")
            return False

    async def get_all_queued_signals(self) -> List[QueuedSignal]:
        async for session in self.session_factory():
            queued_signal_repo = self.queued_signal_repository_class(session)
            return await queued_signal_repo.get_all_queued_signals()

    async def promote_specific_signal(self, signal_id: uuid.UUID) -> Optional[QueuedSignal]:
        async for session in self.session_factory():
            queued_signal_repo = self.queued_signal_repository_class(session)
            position_group_repo = self.position_group_repository_class(session)

            signal = await queued_signal_repo.get_by_id(signal_id, for_update=True)
            if not signal or signal.status != QueueStatus.QUEUED:
                logger.warning(f"Signal {signal_id} not found or not in queued status for promotion.")
                return None

            active_groups = await position_group_repo.get_active_position_groups(for_update=True)
            existing_group = find_active_group(active_groups, signal.symbol, signal.timeframe)
            is_pyramid_continuation = existing_group is not None

            if await self.execution_pool_manager.request_slot(session, is_pyramid_continuation=is_pyramid_continuation):
                logger.info(f"Promoting specific signal {signal.id} for {signal.symbol}")

                try:
                    current_price = await self.exchange_connector.get_current_price(signal.symbol)
                    if signal.side == "long":
                        loss_percent = ((current_price - signal.entry_price) / signal.entry_price) * Decimal("100")
                    else:
                        loss_percent = ((signal.entry_price - current_price) / signal.entry_price) * Decimal("100")
                    signal.current_loss_percent = loss_percent
                except Exception as e:
                    logger.warning(f"Could not fetch current price for {signal.symbol} during specific promotion: {e}")
                    signal.current_loss_percent = None

                update_data = {
                    "status": QueueStatus.PROMOTED,
                    "promoted_at": datetime.utcnow(),
                    "current_loss_percent": signal.current_loss_percent
                }
                await queued_signal_repo.update(signal.id, update_data)

                if is_pyramid_continuation:
                    await self.position_manager_service.handle_pyramid_continuation(
                        user_id=signal.user_id,
                        signal=signal,
                        existing_position_group=existing_group,
                        risk_config=self.risk_engine_config,
                        dca_grid_config=self.dca_grid_config,
                        total_capital_usd=self.total_capital_usd
                    )
                else:
                    await self.position_manager_service.create_position_group_from_signal(
                        user_id=signal.user_id,
                        signal=signal,
                        risk_config=self.risk_engine_config,
                        dca_grid_config=self.dca_grid_config,
                        total_capital_usd=self.total_capital_usd
                    )
                return signal
            else:
                logger.info(f"No pool slot available for specific signal {signal.id}")
                return None

    async def force_add_specific_signal_to_pool(self, signal_id: uuid.UUID) -> Optional[QueuedSignal]:
        async for session in self.session_factory():
            queued_signal_repo = self.queued_signal_repository_class(session)
            position_group_repo = self.position_group_repository_class(session)

            signal = await queued_signal_repo.get_by_id(signal_id, for_update=True)
            if not signal or signal.status != QueueStatus.QUEUED:
                logger.warning(f"Signal {signal_id} not found or not in queued status for force add.")
                return None

            active_groups = await position_group_repo.get_active_position_groups(for_update=True)
            existing_group = find_active_group(active_groups, signal.symbol, signal.timeframe)
            is_pyramid_continuation = existing_group is not None

            logger.info(f"Forcing signal {signal.id} for {signal.symbol} into active pool.")

            try:
                current_price = await self.exchange_connector.get_current_price(signal.symbol)
                if signal.side == "long":
                    loss_percent = ((current_price - signal.entry_price) / signal.entry_price) * Decimal("100")
                else:
                    loss_percent = ((signal.entry_price - current_price) / signal.entry_price) * Decimal("100")
                signal.current_loss_percent = loss_percent
            except Exception as e:
                logger.warning(f"Could not fetch current price for {signal.symbol} during force add: {e}")
                signal.current_loss_percent = None

            update_data = {
                "status": QueueStatus.PROMOTED,
                "promoted_at": datetime.utcnow(),
                "current_loss_percent": signal.current_loss_percent
            }
            await queued_signal_repo.update(signal.id, update_data)

            if is_pyramid_continuation:
                await self.position_manager_service.handle_pyramid_continuation(
                    user_id=signal.user_id,
                    signal=signal,
                    existing_position_group=existing_group,
                    risk_config=self.risk_engine_config,
                    dca_grid_config=self.dca_grid_config,
                    total_capital_usd=self.total_capital_usd
                )
            else:
                await self.position_manager_service.create_position_group_from_signal(
                    user_id=signal.user_id,
                    signal=signal,
                    risk_config=self.risk_engine_config,
                    dca_grid_config=self.dca_grid_config,
                    total_capital_usd=self.total_capital_usd
                )
            return signal

    async def _promote_highest_priority_signal(self, session: AsyncSession):
        queued_signal_repo = self.queued_signal_repository_class(session)
        position_group_repo = self.position_group_repository_class(session)
        
        promoted_signal = await self.promote_from_queue(session, queued_signal_repo, position_group_repo)

        if promoted_signal:
            active_groups = await position_group_repo.get_active_position_groups(for_update=True)
            existing_group = find_active_group(active_groups, promoted_signal.symbol, promoted_signal.timeframe)
            is_pyramid_continuation = existing_group is not None
            
            if await self.execution_pool_manager.request_slot(session, is_pyramid_continuation=is_pyramid_continuation):
                logger.info(f"Promoting signal {promoted_signal.id} for {promoted_signal.symbol}")
                
                update_data = {
                    "status": QueueStatus.PROMOTED,
                    "promoted_at": datetime.utcnow()
                }
                if promoted_signal.current_loss_percent is not None:
                    update_data["current_loss_percent"] = promoted_signal.current_loss_percent

                await queued_signal_repo.update(promoted_signal.id, update_data)
                
                if is_pyramid_continuation:
                    await self.position_manager_service.handle_pyramid_continuation(
                        user_id=promoted_signal.user_id,
                        signal=promoted_signal,
                        existing_position_group=existing_group,
                        risk_config=self.risk_engine_config,
                        dca_grid_config=self.dca_grid_config,
                        total_capital_usd=self.total_capital_usd
                    )
                else:
                    await self.position_manager_service.create_position_group_from_signal(
                        user_id=promoted_signal.user_id,
                        signal=promoted_signal,
                        risk_config=self.risk_engine_config,
                        dca_grid_config=self.dca_grid_config,
                        total_capital_usd=self.total_capital_usd
                    )
            else:
                logger.info(f"No pool slot available for signal {promoted_signal.id}")
        else:
            logger.debug("No signals in queue to promote.")

    async def promote_from_queue(self, session: AsyncSession, queued_signal_repo: QueuedSignalRepository, position_group_repo: PositionGroupRepository) -> Optional[QueuedSignal]:
        queued_signals = await queued_signal_repo.get_all_queued_signals(for_update=True)
        if not queued_signals:
            return None

        active_groups = await position_group_repo.get_active_position_groups(for_update=True)

        for signal in queued_signals:
            try:
                current_price = await self.exchange_connector.get_current_price(signal.symbol)
                if signal.side == "long":
                    loss_percent = ((current_price - signal.entry_price) / signal.entry_price) * Decimal("100")
                else:
                    loss_percent = ((signal.entry_price - current_price) / signal.entry_price) * Decimal("100")
                signal.current_loss_percent = loss_percent
            except Exception as e:
                logger.warning(f"Could not fetch current price for {signal.symbol}: {e}")
                signal.current_loss_percent = None
        
        prioritized = [(signal, calculate_queue_priority(signal, active_groups)) for signal in queued_signals]
        prioritized.sort(key=lambda x: x[1], reverse=True)
        selected_signal, _ = prioritized[0]
        return selected_signal

    async def start_promotion_task(self, stop_event: asyncio.Event = None):
        if not self._running:
            self._running = True
            self._promotion_task = asyncio.create_task(self._promotion_loop(stop_event))
            logger.info("QueueManagerService promotion task started.")

    async def _promotion_loop(self, stop_event: asyncio.Event = None):
        while self._running:
            try:
                async for session in self.session_factory():
                    await self._promote_highest_priority_signal(session)
                if stop_event:
                    stop_event.set()
                await asyncio.sleep(self.polling_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue promotion loop: {e}")
                await asyncio.sleep(self.polling_interval_seconds)

    async def stop_promotion_task(self):
        if self._running and self._promotion_task:
            self._running = False
            self._promotion_task.cancel()
            try:
                await self._promotion_task
            except asyncio.CancelledError:
                pass
            logger.info("QueueManagerService promotion task stopped.")