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
        logger.debug(f"Entering create_position_group_from_signal for user {user_id}")
        
        # 1. Get user 
        user = await session.get(User, user_id)
        if not user:
            logger.debug("User not found")
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
            logger.debug(f"Decrypted keys. API Key len: {len(api_key)}")
            
            exchange_connector = get_exchange_connector(
                exchange_type=signal.exchange,
                api_key=api_key,
                secret_key=secret_key
            )
        
        logger.debug(f"Got exchange connector: {exchange_connector}")

        # 2. Fetch precision rules
        precision_rules = await exchange_connector.get_precision_rules()
        logger.debug(f"Got precision rules: {precision_rules}")
        symbol_precision = precision_rules.get(signal.symbol, {})

        # 3. Calculate DCA levels and quantities
        dca_levels = self.grid_calculator_service.calculate_dca_levels(
            base_price=signal.entry_price,
            dca_config=dca_grid_config, 
            side=signal.side,
            precision_rules=symbol_precision
        )
        logger.debug(f"Calculated {len(dca_levels)} levels")
        
        dca_levels = self.grid_calculator_service.calculate_order_quantities(
            dca_levels=dca_levels,
            total_capital_usd=total_capital_usd,
            precision_rules=symbol_precision
        )
        logger.debug("Calculated quantities")

        # 4. Create PositionGroup
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
            tp_mode=dca_grid_config.tp_mode, # Get from user config
            tp_aggregate_percent=dca_grid_config.tp_aggregate_percent,
            pyramid_count=0,
            max_pyramids=dca_grid_config.max_pyramids, # Updated to use config
            risk_timer_start=None,
            risk_timer_expires=None
        )
        session.add(new_position_group)
        await session.flush()
        logger.debug(f"Created PG {new_position_group.id}")
        
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
        
        logger.debug(f"About to submit {len(orders_to_submit)} orders")
        # 9. Asynchronously submit all orders
        try:
            for order in orders_to_submit:
                logger.debug(f"Submitting order {order.leg_index}")
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
        
        await self.update_risk_timer(new_position_group.id, risk_config, session=session)
        await self.update_position_stats(new_position_group.id, exchange_connector=exchange_connector, session=session)

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
        
        # Reset risk timer only if it was already running (condition previously met)
        if risk_config.reset_timer_on_replacement and existing_position_group.risk_timer_expires is not None:
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
        
        await self.update_risk_timer(existing_position_group.id, risk_config, session=session)
        await self.update_position_stats(existing_position_group.id, exchange_connector=exchange_connector, session=session)
        
        return existing_position_group

    async def handle_exit_signal(self, position_group_id: uuid.UUID):
        """
        Handles an exit signal for a position group.
        1. Cancels all open DCA orders.
        2. Places a market order to close the total filled quantity.
        """
        async with self.session_factory() as session:
            # Re-fetch position group with orders attached in this session
            position_group_repo = self.position_group_repository_class(session)
            position_group = await position_group_repo.get_with_orders(position_group_id)
            
            if not position_group:
                logger.error(f"PositionGroup {position_group_id} not found for exit signal.")
                return

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


    async def update_risk_timer(self, position_group_id: uuid.UUID, risk_config: RiskEngineConfig, session: AsyncSession = None):
        if session:
            await self._execute_update_risk_timer(session, position_group_id, risk_config)
        else:
            async with self.session_factory() as new_session:
                await self._execute_update_risk_timer(new_session, position_group_id, risk_config)
                await new_session.commit()

    async def _execute_update_risk_timer(self, session: AsyncSession, position_group_id: uuid.UUID, risk_config: RiskEngineConfig):
        position_group_repo = self.position_group_repository_class(session)
        position_group = await position_group_repo.get(position_group_id)

        if not position_group:
            return

        # Check if timer is already set/active to avoid resetting it unless intended (though this logic mainly STARTS it)
        if position_group.risk_timer_expires is not None:
             # Timer already running.
             # Logic for resetting on replacement is handled in handle_pyramid_continuation
             return

        timer_started = False
        if risk_config.timer_start_condition == "after_5_pyramids" and position_group.pyramid_count >= 5:
            timer_started = True
        elif risk_config.timer_start_condition == "after_all_dca_submitted" and position_group.pyramid_count >= 5:
            # Assuming 5 pyramids means all DCA submitted for the grid logic usually
            timer_started = True
        elif risk_config.timer_start_condition == "after_all_dca_filled" and position_group.filled_dca_legs == position_group.total_dca_legs:
            timer_started = True

        if timer_started:
            expires_at = datetime.utcnow() + timedelta(minutes=risk_config.post_full_wait_minutes)
            position_group.risk_timer_expires = expires_at
            await position_group_repo.update(position_group)
            # await session.commit() -> handled by caller or wrapper
            logger.info(f"Risk timer started for PositionGroup {position_group.id}. Expires at {expires_at}")


    async def update_position_stats(self, group_id: uuid.UUID, exchange_connector: ExchangeInterface, session: AsyncSession = None):
        """
        Recalculates total filled quantity and weighted average entry price for a position group.
        """
        if session:
            await self._execute_update_position_stats(session, group_id, exchange_connector)
        else:
            async with self.session_factory() as new_session:
                await self._execute_update_position_stats(new_session, group_id, exchange_connector)
                await new_session.commit() # Commit here when a new session is created

    async def _execute_update_position_stats(self, session: AsyncSession, group_id: uuid.UUID, exchange_connector: ExchangeInterface):
        position_group_repo = self.position_group_repository_class(session)
        position_group = await position_group_repo.get(group_id)
        if not position_group:
            logger.error(f"PositionGroup {group_id} not found for stats update.")
            return

        # Query DCAOrder directly
        from sqlalchemy import select
        from app.models.dca_order import DCAOrder
        from app.models.pyramid import Pyramid, PyramidStatus

        stmt = select(DCAOrder).where(DCAOrder.group_id == group_id)
        result = await session.execute(stmt)
        all_orders = result.scalars().all()
        
        # --- 1. Update Pyramid Statuses ---
        pyramid_orders = {}
        for order in all_orders:
            if order.pyramid_id:
                pyramid_orders.setdefault(order.pyramid_id, []).append(order)

        for pyramid_id, orders_in_pyramid in pyramid_orders.items():
            pyramid = await session.get(Pyramid, pyramid_id)
            if not pyramid: continue

            any_order_submitted_or_filled = any(
                o.status in [OrderStatus.OPEN, OrderStatus.FILLED] 
                for o in orders_in_pyramid
            )
            all_orders_for_pyramid_filled = all(o.status == OrderStatus.FILLED for o in orders_in_pyramid)
            
            if all_orders_for_pyramid_filled and pyramid.status != PyramidStatus.FILLED:
                pyramid.status = PyramidStatus.FILLED
                logger.info(f"Pyramid {pyramid.id} status updated to FILLED.")
            elif any_order_submitted_or_filled and pyramid.status == PyramidStatus.PENDING:
                pyramid.status = PyramidStatus.SUBMITTED
                logger.info(f"Pyramid {pyramid.id} status updated to SUBMITTED.")

        # --- 2. Calculate Stats from Filled Orders (Chronological Replay) ---
        filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
        
        # Sort by filled_at to ensure correct sequence of Entry -> Exit
        # If filled_at is missing, fallback to created_at
        filled_orders.sort(key=lambda x: x.filled_at or x.created_at or datetime.min)
        
        current_qty = Decimal("0")
        current_invested_usd = Decimal("0")
        total_realized_pnl = Decimal("0")
        
        # Track weighted avg dynamically
        current_avg_price = Decimal("0")
        
        for o in filled_orders:
            # Normalize side
            order_side = o.side.lower()
            group_side = position_group.side.lower()
            
            qty = o.filled_quantity
            price = o.avg_fill_price or o.price
            
            is_entry = False
            if group_side == "long" and order_side == "buy":
                is_entry = True
            elif group_side == "short" and order_side == "sell":
                is_entry = True

            if is_entry:
                # --- ENTRY ---
                new_invested = current_invested_usd + (qty * price)
                new_qty = current_qty + qty
                
                if new_qty > 0:
                    current_avg_price = new_invested / new_qty
                
                current_qty = new_qty
                current_invested_usd = new_invested
                
            else:
                # --- EXIT ---
                # Calculate PnL against CURRENT average entry
                if group_side == "long":
                    trade_pnl = (price - current_avg_price) * qty
                else:
                    trade_pnl = (current_avg_price - price) * qty
                
                total_realized_pnl += trade_pnl
                
                # Reduce Quantity
                current_qty -= qty
                # Reduce Invested Amount proportionally (maintain avg price)
                current_invested_usd = current_qty * current_avg_price

                # Safety: If qty goes to 0 or negative (shouldn't happen), reset
                if current_qty <= 0:
                    current_qty = Decimal("0")
                    current_invested_usd = Decimal("0")
                    current_avg_price = Decimal("0") 

        # --- 3. Update Position Group Stats ---
        position_group.weighted_avg_entry = current_avg_price
        position_group.total_invested_usd = current_invested_usd
        position_group.total_filled_quantity = current_qty
        position_group.realized_pnl_usd = total_realized_pnl
        
        # Calculate Unrealized PnL
        current_price = await exchange_connector.get_current_price(position_group.symbol)
        
        if current_qty > 0 and current_avg_price > 0:
            if position_group.side.lower() == "long":
                position_group.unrealized_pnl_usd = (current_price - current_avg_price) * current_qty
            else:
                position_group.unrealized_pnl_usd = (current_avg_price - current_price) * current_qty
            
            # ROI % based on current invested capital
            if position_group.total_invested_usd > 0:
                position_group.unrealized_pnl_percent = (position_group.unrealized_pnl_usd / position_group.total_invested_usd) * Decimal("100")
            else:
                 position_group.unrealized_pnl_percent = Decimal("0")
        else:
            position_group.unrealized_pnl_usd = Decimal("0")
            position_group.unrealized_pnl_percent = Decimal("0")

        # Update Legs Count
        # Count only ENTRY legs that are filled to track grid progress
        filled_entry_legs = sum(1 for o in filled_orders if o.side.lower() == position_group.side.lower())
        position_group.filled_dca_legs = filled_entry_legs

        # Status Transition Logic
        if position_group.status in [PositionGroupStatus.LIVE, PositionGroupStatus.PARTIALLY_FILLED]:
             if filled_entry_legs >= position_group.total_dca_legs:
                 position_group.status = PositionGroupStatus.ACTIVE
                 logger.info(f"PositionGroup {group_id} transitioned to ACTIVE")
             elif filled_entry_legs > 0:
                 position_group.status = PositionGroupStatus.PARTIALLY_FILLED
        
        # Auto-close check
        if current_qty <= 0 and len(filled_orders) > 0 and position_group.status not in [PositionGroupStatus.CLOSED, PositionGroupStatus.CLOSING]:
             position_group.status = PositionGroupStatus.CLOSED
             position_group.closed_at = datetime.utcnow()
             logger.info(f"PositionGroup {group_id} auto-closed. Realized PnL: {total_realized_pnl}")
        
        await position_group_repo.update(position_group)

        # --- 4. Aggregate/Hybrid TP Execution Logic ---
        # Only if we are holding a position and not already closing
        if current_qty > 0 and position_group.status not in [PositionGroupStatus.CLOSING, PositionGroupStatus.CLOSED]:
            should_execute_tp = False
            
            if position_group.tp_mode in ["aggregate", "hybrid"] and position_group.tp_aggregate_percent > 0:
                aggregate_tp_price = Decimal("0")
                if position_group.side.lower() == "long":
                    aggregate_tp_price = current_avg_price * (Decimal("1") + position_group.tp_aggregate_percent / Decimal("100"))
                    if current_price >= aggregate_tp_price:
                        should_execute_tp = True
                else: # Short
                    aggregate_tp_price = current_avg_price * (Decimal("1") - position_group.tp_aggregate_percent / Decimal("100"))
                    if current_price <= aggregate_tp_price:
                        should_execute_tp = True
                
                if should_execute_tp:
                    logger.info(f"Aggregate TP Triggered for Group {group_id} at {current_price} (Target: {aggregate_tp_price})")
                    
                    # Instantiate OrderService
                    order_service = self.order_service_class(
                        session=session,
                        user=self.user,
                        exchange_connector=exchange_connector
                    )
                    
                    # 1. Cancel all open orders (remove Limit TPs)
                    await order_service.cancel_open_orders_for_group(group_id)
                    
                    # 2. Execute Market Close for remaining quantity
                    close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
                    await order_service.place_market_order(
                        user_id=self.user.id,
                        exchange=position_group.exchange,
                        symbol=position_group.symbol,
                        side=close_side,
                        quantity=current_qty,
                        position_group_id=group_id,
                        record_in_db=True
                    )
                    
                    # Mark group as CLOSING
                    position_group.status = PositionGroupStatus.CLOSING
                    await position_group_repo.update(position_group)
                    
                    logger.info(f"Executed Aggregate TP Market Close for Group {group_id}")

        pass
