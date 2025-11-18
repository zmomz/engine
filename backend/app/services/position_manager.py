import logging
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.queued_signal import QueuedSignal
from app.repositories.position_group import PositionGroupRepository
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.schemas.webhook_payloads import TradingViewSignal
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService

logger = logging.getLogger(__name__)

class PositionManagerService:
    def __init__(
        self,
        session: AsyncSession,
        position_group_repository_class: type[PositionGroupRepository],
        grid_calculator_service: GridCalculatorService,
        order_service_class: type[OrderService]
    ):
        self.session = session
        self.position_group_repository_class = position_group_repository_class
        self.grid_calculator_service = grid_calculator_service
        self.order_service_class = order_service_class
        self.position_group_repo = self.position_group_repository_class(self.session)

    async def create_position_group_from_signal(
        self,
        user_id: uuid.UUID,
        signal: QueuedSignal,
        risk_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ) -> PositionGroup:
        # Calculate DCA levels and quantities
        # Assuming signal.entry_price is the base price for the first leg
        precision_rules = {} # TODO: Fetch actual precision rules from exchange abstraction
        dca_levels = self.grid_calculator_service.calculate_dca_levels(
            base_price=signal.entry_price,
            dca_config=dca_grid_config.root,
            side=signal.side,
            precision_rules=precision_rules # Placeholder
        )
        dca_levels = self.grid_calculator_service.calculate_order_quantities(
            dca_levels=dca_levels,
            total_capital_usd=total_capital_usd,
            precision_rules=precision_rules # Placeholder
        )

        # Create PositionGroup
        risk_timer_start = datetime.utcnow()
        risk_timer_expires = risk_timer_start + timedelta(minutes=risk_config.post_full_wait_minutes)
        
        new_position_group = PositionGroup(
            user_id=user_id,
            exchange=signal.exchange,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=signal.side,
            status=PositionGroupStatus.LIVE, # Or WAITING, depending on further logic
            total_dca_legs=len(dca_levels),
            base_entry_price=signal.entry_price,
            weighted_avg_entry=signal.entry_price, # Initial
            total_invested_usd=Decimal("0"), # Will be updated on fills
            total_filled_quantity=Decimal("0"), # Will be updated on fills
            tp_mode="per_leg", # TODO: Get from user config
            pyramid_count=0,
            max_pyramids=5, # TODO: Get from user config
            risk_timer_start=risk_timer_start,
            risk_timer_expires=risk_timer_expires
        )
        
        await self.position_group_repo.create(new_position_group)
        await self.session.commit()
        
        logger.info(f"Created new PositionGroup {new_position_group.id} from signal {signal.id}")
        return new_position_group

    async def handle_pyramid_continuation(
        self,
        user_id: uuid.UUID,
        signal: QueuedSignal,
        existing_position_group: PositionGroup,
        risk_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ) -> PositionGroup:
        # Increment pyramid count
        existing_position_group.pyramid_count += 1
        existing_position_group.replacement_count += 1 # Also increment replacement count

        # Reset risk timer if configured
        if risk_config.reset_timer_on_replacement and existing_position_group.risk_timer_expires:
            existing_position_group.risk_timer_start = datetime.utcnow()
            existing_position_group.risk_timer_expires = existing_position_group.risk_timer_start + timedelta(minutes=risk_config.post_full_wait_minutes)

        # TODO: Generate new DCA orders for the new pyramid
        # This will involve calling GridCalculatorService again with the new pyramid's base price
        # and associating the new DCA orders with the existing_position_group and a new Pyramid model

        await self.position_group_repo.update(existing_position_group)
        await self.session.commit()
        logger.info(f"Handled pyramid continuation for PositionGroup {existing_position_group.id} from signal {signal.id}")
        return existing_position_group

    async def handle_exit_signal(self, position_group: PositionGroup):
        """
        Handles an exit signal for a position group.
        1. Cancels all open DCA orders.
        2. Places a market order to close the total filled quantity.
        """
        # The OrderService needs its own session and repositories
        order_service = self.order_service_class(self.session) # Assuming OrderService can be instantiated like this

        # 1. Cancel open orders
        await order_service.cancel_open_orders_for_group(position_group.id)
        logger.info(f"Cancelled open orders for PositionGroup {position_group.id}")

        # 2. Calculate total filled quantity
        total_filled_quantity = sum(
            order.filled_quantity 
            for order in position_group.dca_orders 
            if order.status == OrderStatus.FILLED
        )

        if total_filled_quantity > 0:
            # 3. Close the position
            await order_service.close_position_market(
                position_group=position_group,
                quantity_to_close=total_filled_quantity
            )
            logger.info(f"Placed market order to close {total_filled_quantity} for PositionGroup {position_group.id}")
        else:
            logger.info(f"No filled quantity to close for PositionGroup {position_group.id}")

        # TODO: Update PositionGroup status to CLOSING/CLOSED
        # position_group.status = PositionGroupStatus.CLOSING
        # await position_group_repo.update(position_group)
        # await self.session.commit()


    async def update_risk_timer(self, position_group_id: uuid.UUID, risk_config: RiskEngineConfig):
        position_group = await self.position_group_repo.get_by_id(position_group_id)

        if not position_group:
            return

        timer_started = False
        if risk_config.timer_start_condition == "after_5_pyramids" and position_group.pyramid_count >= 5:
            timer_started = True
        elif risk_config.timer_start_condition == "after_all_dca_submitted" and position_group.pyramid_count >= 5:
            # This condition is met when all pyramids are present, assuming dca are submitted with them
            timer_started = True
        elif risk_config.timer_start_condition == "after_all_dca_filled" and position_group.filled_dca_legs == position_group.total_dca_legs:
            timer_started = True

        if timer_started:
            expires_at = datetime.utcnow() + timedelta(minutes=risk_config.post_full_wait_minutes)
            await self.position_group_repo.update(position_group_id, {"risk_timer_expires": expires_at})
            logger.info(f"Risk timer started for PositionGroup {position_group.id}. Expires at {expires_at}")


    # TODO: Add methods for updating position group PnL, status, etc.