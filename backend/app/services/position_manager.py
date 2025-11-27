import logging
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import asyncio
import json

from typing import Callable, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.pyramid import Pyramid, PyramidStatus
from app.models.queued_signal import QueuedSignal
from app.models.user import User
from app.repositories.position_group import PositionGroupRepository
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.schemas.webhook_payloads import WebhookPayload
from app.services.grid_calculator import GridCalculatorService
from app.services.order_management import OrderService
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.core.security import EncryptionService
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class UserNotFoundException(Exception):
    """Exception raised when a user is not found."""
    pass

class PositionManagerService:
    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        user: "User",
        position_group_repository_class: type[PositionGroupRepository],
        grid_calculator_service: GridCalculatorService,
        order_service_class: type[OrderService],
        exchange_connector: ExchangeInterface
    ):
        self.session_factory = session_factory
        self.user = user
        self.position_group_repository_class = position_group_repository_class
        self.grid_calculator_service = grid_calculator_service
        self.order_service_class = order_service_class
        self.exchange_connector = exchange_connector
        self.order_service = None

    async def create_position_group_from_signal(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        signal: QueuedSignal,
        risk_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ) -> PositionGroup:
        print(f"DEBUG: Entering create_position_group_from_signal for user {user_id}")
        
        # 1. Get user 
        user = await session.get(User, user_id)
        if not user:
            print("DEBUG: User not found")
            raise UserNotFoundException(f"User {user_id} not found")

        if self.exchange_connector:
            exchange_connector = self.exchange_connector
        else:
            # Decrypt API keys to instantiate exchange connector
            encryption_service = EncryptionService() 
            
            # Handle multi-exchange keys
            encrypted_data = user.encrypted_api_keys
            if isinstance(encrypted_data, dict):
                 if signal.exchange in encrypted_data:
                     encrypted_data = encrypted_data[signal.exchange]
                 elif "encrypted_data" not in encrypted_data:
                     raise ValueError(f"No API keys found for exchange {signal.exchange}")

            api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
            print(f"DEBUG: Decrypted keys. API Key len: {len(api_key)}")
            
            exchange_connector = get_exchange_connector(
                exchange_type=signal.exchange,
                api_key=api_key,
                secret_key=secret_key
            )
        
        print(f"DEBUG: Got exchange connector: {exchange_connector}")

        # 2. Fetch precision rules
        precision_rules = await exchange_connector.get_precision_rules()
        print(f"DEBUG: Got precision rules: {precision_rules}")
        symbol_precision = precision_rules.get(signal.symbol, {})

        # 3. Calculate DCA levels and quantities
        dca_levels = self.grid_calculator_service.calculate_dca_levels(
            base_price=signal.entry_price,
            dca_config=dca_grid_config, 
            side=signal.side,
            precision_rules=symbol_precision
        )
        print(f"DEBUG: Calculated {len(dca_levels)} levels")
        
        dca_levels = self.grid_calculator_service.calculate_order_quantities(
            dca_levels=dca_levels,
            total_capital_usd=total_capital_usd,
            precision_rules=symbol_precision
        )
        print("DEBUG: Calculated quantities")

        # 4. Create PositionGroup
        risk_timer_start = datetime.utcnow()
        risk_timer_expires = risk_timer_start + timedelta(minutes=risk_config.post_full_wait_minutes)
        
        new_position_group = PositionGroup(
            user_id=user_id,
            exchange=signal.exchange,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=signal.side,
            status=PositionGroupStatus.LIVE,
            total_dca_legs=len(dca_levels),
            base_entry_price=signal.entry_price,
            weighted_avg_entry=signal.entry_price,
            tp_mode="per_leg", # TODO: Get from user config
            pyramid_count=0,
            max_pyramids=5, # TODO: Get from user config
            risk_timer_start=risk_timer_start,
            risk_timer_expires=risk_timer_expires
        )
        session.add(new_position_group)
        await session.flush()
        print(f"DEBUG: Created PG {new_position_group.id}")
        
        # 5. Create Initial Pyramid
        new_pyramid = Pyramid(
            group_id=new_position_group.id,
            pyramid_index=0,
            entry_price=signal.entry_price,
            status=PyramidStatus.PENDING,
            dca_config=json.loads(dca_grid_config.json())
        )
        session.add(new_pyramid)
        await session.flush()

        # 6. Instantiate OrderService
        order_service = self.order_service_class(
            session=session,
            user=user,
            exchange_connector=exchange_connector
        )

        # 7. Create DCAOrder objects
        orders_to_submit = []
        order_side = "buy" if signal.side == "long" else "sell"
        
        for i, level in enumerate(dca_levels):
            dca_order = DCAOrder(
                group_id=new_position_group.id,
                pyramid_id=new_pyramid.id,
                leg_index=i,
                symbol=signal.symbol,
                side=order_side,
                order_type="limit",
                price=level['price'],
                quantity=level['quantity'],
                status=OrderStatus.PENDING,
                gap_percent=level.get('gap_percent', Decimal("0")),
                weight_percent=level.get('weight_percent', Decimal("0")),
                tp_percent=level.get('tp_percent', Decimal("0")),
                tp_price=level.get('tp_price', Decimal("0")),
            )
            session.add(dca_order)
            orders_to_submit.append(dca_order)
        
        print(f"DEBUG: About to submit {len(orders_to_submit)} orders")
        # 9. Asynchronously submit all orders
        try:
            for order in orders_to_submit:
                print(f"DEBUG: Submitting order {order.leg_index}")
                await order_service.submit_order(order)
        except Exception as e:
            logger.error(f"Failed to submit orders for PositionGroup {new_position_group.id}: {e}")
            new_position_group.status = PositionGroupStatus.FAILED
            # We don't raise here to allow the transaction to commit the FAILED status
            # But the caller might need to know. 
            # However, if we suppress, the PG is saved as FAILED.
            pass
        
        # Update pyramid status after orders are submitted
        new_pyramid.status = PyramidStatus.SUBMITTED
        await session.flush() # Ensure pyramid status is updated

        logger.info(f"Created new PositionGroup {new_position_group.id} and submitted {len(orders_to_submit)} DCA orders.")
        
        return new_position_group

    async def handle_pyramid_continuation(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        signal: QueuedSignal,
        existing_position_group: PositionGroup,
        risk_config: RiskEngineConfig,
        dca_grid_config: DCAGridConfig,
        total_capital_usd: Decimal
    ) -> PositionGroup:
        # 1. Get user 
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFoundException(f"User {user_id} not found")

        if self.exchange_connector:
            exchange_connector = self.exchange_connector
        else:
            # Decrypt API keys
            encryption_service = EncryptionService() 
            
            # Handle multi-exchange keys
            encrypted_data = user.encrypted_api_keys
            if isinstance(encrypted_data, dict):
                 if signal.exchange in encrypted_data:
                     encrypted_data = encrypted_data[signal.exchange]
                 elif "encrypted_data" not in encrypted_data:
                     raise ValueError(f"No API keys found for exchange {signal.exchange}")

            api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
            exchange_connector = get_exchange_connector(
                exchange_type=signal.exchange,
                api_key=api_key,
                secret_key=secret_key
            )

        # 2. Fetch precision rules
        precision_rules = await exchange_connector.get_precision_rules()
        symbol_precision = precision_rules.get(signal.symbol, {})

        # 3. Calculate DCA levels for this NEW pyramid
        dca_levels = self.grid_calculator_service.calculate_dca_levels(
            base_price=signal.entry_price,
            dca_config=dca_grid_config,
            side=signal.side,
            precision_rules=symbol_precision
        )
        dca_levels = self.grid_calculator_service.calculate_order_quantities(
            dca_levels=dca_levels,
            total_capital_usd=total_capital_usd,
            precision_rules=symbol_precision
        )

        # 4. Update PositionGroup Stats
        existing_position_group.pyramid_count += 1
        existing_position_group.replacement_count += 1
        existing_position_group.total_dca_legs += len(dca_levels)
        
        # Reset risk timer if configured
        if risk_config.reset_timer_on_replacement:
            existing_position_group.risk_timer_start = datetime.utcnow()
            existing_position_group.risk_timer_expires = existing_position_group.risk_timer_start + timedelta(minutes=risk_config.post_full_wait_minutes)

        # 5. Create New Pyramid
        new_pyramid = Pyramid(
            group_id=existing_position_group.id,
            pyramid_index=existing_position_group.pyramid_count,
            entry_price=signal.entry_price,
            status=PyramidStatus.PENDING,
            dca_config=json.loads(dca_grid_config.json())
        )
        session.add(new_pyramid)
        await session.flush()

        # 6. Instantiate OrderService
        order_service = self.order_service_class(
            session=session,
            user=user,
            exchange_connector=exchange_connector
        )

        # 7. Create DCAOrder objects
        orders_to_submit = []
        order_side = "buy" if signal.side == "long" else "sell"
        
        for i, level in enumerate(dca_levels):
            dca_order = DCAOrder(
                group_id=existing_position_group.id,
                pyramid_id=new_pyramid.id,
                leg_index=i,
                symbol=signal.symbol,
                side=order_side,
                order_type="limit",
                price=level['price'],
                quantity=level['quantity'],
                status=OrderStatus.PENDING,
                gap_percent=level.get('gap_percent', Decimal("0")),
                weight_percent=level.get('weight_percent', Decimal("0")),
                tp_percent=level.get('tp_percent', Decimal("0")),
                tp_price=level.get('tp_price', Decimal("0")),
            )
            session.add(dca_order)
            orders_to_submit.append(dca_order)

        for order in orders_to_submit:
            await order_service.submit_order(order)

        logger.info(f"Handled pyramid continuation for PositionGroup {existing_position_group.id} from signal {signal.id}. Created {len(orders_to_submit)} new orders.")
        return existing_position_group

    async def handle_exit_signal(self, position_group: PositionGroup):
        """
        Handles an exit signal for a position group.
        1. Cancels all open DCA orders.
        2. Places a market order to close the total filled quantity.
        """
        async with self.session_factory() as session:
            order_service = self.order_service_class(session=session, user=self.user, exchange_connector=self.exchange_connector)

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

            position_group_repo = self.position_group_repository_class(session)
            position_group.status = PositionGroupStatus.CLOSED
            
            current_price = await self.exchange_connector.get_current_price(position_group.symbol)
            
            exit_value = total_filled_quantity * current_price
            cost_basis = position_group.total_invested_usd
            
            if position_group.side == "long":
                realized_pnl = exit_value - cost_basis
            else:
                realized_pnl = cost_basis - exit_value
                
            position_group.realized_pnl_usd = realized_pnl
            position_group.unrealized_pnl_usd = Decimal("0")
            position_group.closed_at = datetime.utcnow()

            await position_group_repo.update(position_group)
            await session.commit()
            logger.info(f"PositionGroup {position_group.id} closed. Realized PnL: {realized_pnl}")


    async def update_risk_timer(self, position_group_id: uuid.UUID, risk_config: RiskEngineConfig):
        async with self.session_factory() as session:
            position_group_repo = self.position_group_repository_class(session)
            position_group = await position_group_repo.get_by_id(position_group_id)

            if not position_group:
                return

            timer_started = False
            if risk_config.timer_start_condition == "after_5_pyramids" and position_group.pyramid_count >= 5:
                timer_started = True
            elif risk_config.timer_start_condition == "after_all_dca_submitted" and position_group.pyramid_count >= 5:
                timer_started = True
            elif risk_config.timer_start_condition == "after_all_dca_filled" and position_group.filled_dca_legs == position_group.total_dca_legs:
                timer_started = True

            if timer_started:
                expires_at = datetime.utcnow() + timedelta(minutes=risk_config.post_full_wait_minutes)
                position_group.risk_timer_expires = expires_at
                await position_group_repo.update(position_group)
                await session.commit()
                logger.info(f"Risk timer started for PositionGroup {position_group.id}. Expires at {expires_at}")


    async def update_position_stats(self, group_id: uuid.UUID, session: AsyncSession = None):
        """
        Recalculates total filled quantity and weighted average entry price for a position group.
        """
        if session:
            await self._execute_update_position_stats(session, group_id)
        else:
            async with self.session_factory() as new_session:
                await self._execute_update_position_stats(new_session, group_id)
                await new_session.commit() # Commit here when a new session is created

    async def _execute_update_position_stats(self, session: AsyncSession, group_id: uuid.UUID):
        position_group_repo = self.position_group_repository_class(session)
        position_group = await position_group_repo.get(group_id)
        if not position_group:
            logger.error(f"PositionGroup {group_id} not found for stats update.")
            return

        # Query DCAOrder directly instead of relying on the relationship
        # because the relationship has lazy='noload' which prevents loading
        from sqlalchemy import select
        from app.models.dca_order import DCAOrder
        from app.models.pyramid import Pyramid, PyramidStatus # Import Pyramid and PyramidStatus

        stmt = select(DCAOrder).where(DCAOrder.group_id == group_id)
        result = await session.execute(stmt)
        all_orders = result.scalars().all()
        
        # Group orders by pyramid_id
        pyramid_orders = {}
        for order in all_orders:
            pyramid_orders.setdefault(order.pyramid_id, []).append(order)

        # Update pyramid statuses based on their DCA orders
        for pyramid_id, orders_in_pyramid in pyramid_orders.items():
            pyramid = await session.get(Pyramid, pyramid_id)
            if not pyramid: # Should not happen if pyramid_orders map is built correctly
                continue

            any_order_submitted_or_filled = any(
                o.status in [OrderStatus.OPEN, OrderStatus.FILLED] 
                for o in orders_in_pyramid
            )
            all_orders_for_pyramid_filled = all(o.status == OrderStatus.FILLED for o in orders_in_pyramid)
            
            if all_orders_for_pyramid_filled and pyramid.status != PyramidStatus.FILLED:
                pyramid.status = PyramidStatus.FILLED
                logger.info(f"Pyramid {pyramid.id} status updated to FILLED.")
                # No need to flush here, outer commit will handle it
            elif any_order_submitted_or_filled and pyramid.status == PyramidStatus.PENDING:
                pyramid.status = PyramidStatus.SUBMITTED
                logger.info(f"Pyramid {pyramid.id} status updated to SUBMITTED (some orders submitted/filled).")
                # No need to flush here, outer commit will handle it
        
        filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
        
        logger.info(f"PositionGroup {group_id}: Found {len(filled_orders)} filled orders out of {len(all_orders)} total orders")
        
        total_qty_in = Decimal("0")
        total_cost_in = Decimal("0")
        realized_pnl = Decimal("0")
        total_qty_out = Decimal("0")
        
        for o in filled_orders:
            qty = o.filled_quantity
            price = o.avg_fill_price or o.price
            total_qty_in += qty
            total_cost_in += qty * price
            
            logger.debug(f"Order {o.id}, Status: {o.status}, TP Hit: {o.tp_hit}, Qty: {qty}, Price: {price}")
            
            if o.tp_hit:
                total_qty_out += qty
                exit_val = qty * o.tp_price
                entry_val = qty * price
                
                if position_group.side == "long":
                    realized_pnl += (exit_val - entry_val)
                else:
                    realized_pnl += (entry_val - exit_val)
                logger.debug(f"PnL Accumulated: {realized_pnl}")
        
        net_qty = total_qty_in - total_qty_out
        
        if total_qty_in > 0:
            avg_entry = total_cost_in / total_qty_in
            position_group.weighted_avg_entry = avg_entry
            position_group.total_filled_quantity = net_qty
            position_group.total_invested_usd = net_qty * avg_entry
            position_group.realized_pnl_usd = realized_pnl
            
            position_group.filled_dca_legs = len(filled_orders)
            
            if position_group.status == PositionGroupStatus.LIVE:
                    if len(filled_orders) == len(position_group.dca_orders):
                        position_group.status = PositionGroupStatus.ACTIVE
                    else:
                        position_group.status = PositionGroupStatus.PARTIALLY_FILLED
            elif position_group.status == PositionGroupStatus.PARTIALLY_FILLED:
                    if len(filled_orders) == len(position_group.dca_orders):
                        position_group.status = PositionGroupStatus.ACTIVE
            
            # Auto-close if everything is sold
            if net_qty == 0 and total_qty_in > 0:
                 position_group.status = PositionGroupStatus.CLOSED
                 position_group.closed_at = datetime.utcnow()
                 logger.info(f"PositionGroup {group_id} auto-closed. Realized PnL: {realized_pnl}, Total Qty In: {total_qty_in}, Total Qty Out: {total_qty_out}")

            await position_group_repo.update(position_group)
            
        else:
            logger.debug(f"No filled orders for PositionGroup {group_id} yet.")
        
        pass
