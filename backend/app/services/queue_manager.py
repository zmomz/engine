"""
Service for managing the execution pool and the signal queue for a specific user.
"""
import logging
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.position_group import PositionGroup
from app.models.user import User
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.position_manager import PositionManagerService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.schemas.webhook_payloads import WebhookPayload

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
        session: AsyncSession,
        user: User,
        queued_signal_repository_class: type[QueuedSignalRepository],
        position_group_repository_class: type[PositionGroupRepository],
        exchange_connector: ExchangeInterface,
        execution_pool_manager: ExecutionPoolManager,
        position_manager_service: PositionManagerService,
        risk_engine_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ):
        self.session = session
        self.user = user
        self.queued_signal_repo = queued_signal_repository_class(session)
        self.position_group_repo = position_group_repository_class(session)
        self.exchange_connector = exchange_connector
        self.execution_pool_manager = execution_pool_manager
        self.position_manager_service = position_manager_service
        self.risk_engine_config = risk_engine_config
        self.dca_grid_config = dca_grid_config
        self.total_capital_usd = total_capital_usd

    async def add_signal_to_queue(self, signal: WebhookPayload):
        side_mapping = {"buy": "long", "sell": "short", "long": "long", "short": "short"}
        position_side = side_mapping.get(signal.execution_intent.side)

        if not position_side:
            logger.warning(f"Invalid side '{signal.execution_intent.side}' received.")
            return

        existing_signal = await self.queued_signal_repo.get_by_symbol_timeframe_side(
            signal.tv.symbol,
            signal.tv.timeframe,
            position_side
        )

        if existing_signal:
            existing_signal.replacement_count += 1
            existing_signal.entry_price = Decimal(str(signal.tv.entry_price))
            existing_signal.signal_payload = signal.model_dump()
            existing_signal.queued_at = datetime.utcnow()
            await self.queued_signal_repo.update(existing_signal)
            await self.session.commit()
            logger.info(f"Replaced queued signal {existing_signal.id}. New replacement count: {existing_signal.replacement_count}")
        else:
            new_signal = QueuedSignal(
                user_id=self.user.id,
                exchange=signal.tv.exchange.lower(),
                symbol=signal.tv.symbol,
                timeframe=signal.tv.timeframe,
                side=position_side,
                entry_price=Decimal(str(signal.tv.entry_price)),
                signal_payload=signal.model_dump(),
                status=QueueStatus.QUEUED.value,
                queued_at=datetime.utcnow()
            )
            await self.queued_signal_repo.create(new_signal)
            await self.session.commit()
            logger.info(f"Added new signal {new_signal.id} to queue for {new_signal.symbol}")

    async def promote_highest_priority_signal(self):
        queued_signals = await self.queued_signal_repo.get_all_queued_signals_for_user(self.user.id, for_update=True)
        if not queued_signals:
            return

        active_groups = await self.position_group_repo.get_active_position_groups_for_user(self.user.id, for_update=True)

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

        is_pyramid_continuation = find_active_group(active_groups, selected_signal.symbol, selected_signal.timeframe) is not None

        if await self.execution_pool_manager.request_slot(is_pyramid_continuation=is_pyramid_continuation):
            logger.info(f"Promoting signal {selected_signal.id} for {selected_signal.symbol}")

            selected_signal.status = QueueStatus.PROMOTED.value
            selected_signal.promoted_at = datetime.utcnow()
            await self.queued_signal_repo.update(selected_signal)

            if is_pyramid_continuation:
                existing_group = find_active_group(active_groups, selected_signal.symbol, selected_signal.timeframe)
                await self.position_manager_service.handle_pyramid_continuation(
                    user_id=self.user.id,
                    signal=selected_signal,
                    existing_position_group=existing_group,
                    risk_config=self.risk_engine_config,
                    dca_grid_config=self.dca_grid_config,
                    total_capital_usd=self.total_capital_usd
                )
            else:
                await self.position_manager_service.create_position_group_from_signal(
                    user_id=self.user.id,
                    signal=selected_signal,
                    risk_config=self.risk_engine_config,
                    dca_grid_config=self.dca_grid_config,
                    total_capital_usd=self.total_capital_usd
                )
            await self.session.commit()
        else:
            logger.info(f"No pool slot available for user {self.user.username}")
