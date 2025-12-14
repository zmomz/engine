import logging
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import asyncio
import json

from typing import Callable, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

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
from app.services.telegram_signal_helper import broadcast_entry_signal, broadcast_exit_signal
from app.core.security import EncryptionService
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class UserNotFoundException(Exception):
    """Exception raised when a user is not found."""
    pass


class DuplicatePositionException(Exception):
    """Exception raised when attempting to create a duplicate active position."""
    pass

class PositionManagerService:
    def __init__(
        self,
        session_factory: Callable[..., AsyncSession],
        user: "User",
        position_group_repository_class: type[PositionGroupRepository],
        grid_calculator_service: GridCalculatorService,
        order_service_class: type[OrderService],

    ):
        self.session_factory = session_factory
        self.user = user
        self.position_group_repository_class = position_group_repository_class
        self.grid_calculator_service = grid_calculator_service
        self.order_service_class = order_service_class

        self.order_service = None

    def _get_exchange_connector_for_user(self, user: User, exchange_name: str) -> ExchangeInterface:
        encrypted_data = user.encrypted_api_keys
        exchange_key = exchange_name.lower()

        if isinstance(encrypted_data, dict):
            if exchange_key in encrypted_data:
                exchange_config = encrypted_data[exchange_key]
            elif "encrypted_data" in encrypted_data and len(encrypted_data) == 1: # Old single-key format might be directly in 'encrypted_data'
                 exchange_config = encrypted_data # This means the dict itself contains the old single key. Likely needs adjustment.
            else:
                raise ValueError(f"No API keys found for exchange {exchange_name} (normalized: {exchange_key}). Available: {list(encrypted_data.keys()) if encrypted_data else 'None'}")
        elif isinstance(encrypted_data, str):
            # Handle legacy single-key encryption where encrypted_api_keys was a string
            exchange_config = {"encrypted_data": encrypted_data}
        else:
            raise ValueError("Invalid format for encrypted_api_keys. Expected dict or str.")

        return get_exchange_connector(exchange_name, exchange_config)

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

        # Dynamically get exchange connector
        exchange_name = signal.exchange.lower()
        encrypted_data = user.encrypted_api_keys
        exchange_config = {}

        if isinstance(encrypted_data, dict):
            if exchange_name in encrypted_data:
                exchange_config = encrypted_data[exchange_name]
            elif "encrypted_data" in encrypted_data and len(encrypted_data) == 1: # Fallback for old single-key setup
                 exchange_config = encrypted_data
            else:
                raise ValueError(f"No API keys found for exchange {exchange_name} (normalized: {exchange_name}). Available: {list(encrypted_data.keys()) if encrypted_data else 'None'}")
        elif isinstance(encrypted_data, str):
            exchange_config = {"encrypted_data": encrypted_data}
        else:
            raise ValueError("Invalid format for encrypted_api_keys")

        exchange_connector = get_exchange_connector(signal.exchange, exchange_config)
        logger.debug(f"Got exchange connector: {exchange_connector.__class__.__name__}. Config: {{k: v for k, v in exchange_config.items() if k != 'encrypted_data'}}")

        # 2. Fetch precision rules
        precision_rules = await exchange_connector.get_precision_rules()
        symbol_precision = precision_rules.get(signal.symbol, {})
        logger.debug(f"Fetched precision rules for {signal.symbol}: {symbol_precision}")
        logger.debug(f"Keys in precision_rules: {list(precision_rules.keys())}")

        # Check if the symbol exists in precision rules
        if signal.symbol not in precision_rules:
            logger.error(f"Symbol {signal.symbol} not found in precision rules!")
            # Try alternative formatting
            alt_symbol = signal.symbol.replace("/", "")
            logger.debug(f"Trying alternative symbol format: {alt_symbol}")
            if alt_symbol in precision_rules:
                symbol_precision = precision_rules[alt_symbol]
                logger.debug(f"Using alternative symbol format for precision rules")


        # 3. Calculate DCA levels and quantities
        dca_levels = self.grid_calculator_service.calculate_dca_levels(
            base_price=signal.entry_price,
            dca_config=dca_grid_config, 
            side=signal.side,
            precision_rules=symbol_precision,
            pyramid_index=0 # Initial entry is index 0
        )
        logger.debug(f"Calculated {len(dca_levels)} levels")
        
        dca_levels = self.grid_calculator_service.calculate_order_quantities(
            dca_levels=dca_levels,
            total_capital_usd=total_capital_usd,
            precision_rules=symbol_precision
        )
        
        # --- Insert new debug logs here ---


        # 4. Create PositionGroup
        new_position_group = PositionGroup(
            user_id=user_id,
            exchange=signal.exchange.lower(),
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
        try:
            await session.flush()
        except IntegrityError as e:
            await session.rollback()
            if 'uix_active_position_group' in str(e.orig):
                logger.warning(
                    f"Duplicate position rejected: {signal.symbol} {signal.side} "
                    f"on {signal.exchange} tf={signal.timeframe} for user {user_id}"
                )
                raise DuplicatePositionException(
                    f"Active position already exists for {signal.symbol} {signal.side} "
                    f"on timeframe {signal.timeframe}"
                )
            raise  # Re-raise if it's a different integrity error
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
        
        # Determine entry order type from config
        entry_type = dca_grid_config.entry_order_type # "limit" or "market"

        for i, level in enumerate(dca_levels):
            # Only the first leg (Leg 0) respects the entry_type. Subsequent DCA legs are always LIMIT (usually).
            # The requirement: "This applies to the initial entry order for this configuration"
            
            # Default to limit
            current_order_type = "limit"
            current_status = OrderStatus.PENDING
            
            if i == 0:
                if entry_type == "market":
                    current_order_type = "market"
                    current_status = OrderStatus.TRIGGER_PENDING
            
            dca_order = DCAOrder(
                group_id=new_position_group.id,
                pyramid_id=new_pyramid.id,
                leg_index=i,
                symbol=signal.symbol,
                side=order_side,
                order_type=current_order_type,
                price=level['price'],
                quantity=level['quantity'],
                status=current_status,
                gap_percent=level.get('gap_percent', Decimal("0")),
                weight_percent=level.get('weight_percent', Decimal("0")),
                tp_percent=level.get('tp_percent', Decimal("0")),
                tp_price=level.get('tp_price', Decimal("0")),
            )
            session.add(dca_order)
            
            # Only submit if it's NOT a trigger pending order
            # If it's PENDING (Limit), we submit.
            # If it's TRIGGER_PENDING (Market), we WAIT.
            if current_status == OrderStatus.PENDING:
                orders_to_submit.append(dca_order)
            else:
                 logger.info(f"Order leg {i} set to {current_status} (Market Watch). Not submitting yet.")
        
        logger.debug(f"About to submit {len(orders_to_submit)} orders")
        # 9. Asynchronously submit orders (only limit ones for now)
        try:
            for order in orders_to_submit:
                logger.debug(f"Submitting order {order.leg_index}")
                await order_service.submit_order(order)
        except Exception as e:
            logger.error(f"Failed to submit orders for PositionGroup {new_position_group.id}: {e}")
            new_position_group.status = PositionGroupStatus.FAILED
            pass
        
        # Update pyramid status after orders are submitted
        new_pyramid.status = PyramidStatus.SUBMITTED
        await session.flush()
        logger.info(f"Pyramid {new_pyramid.id} status updated to SUBMITTED after order submission.")

        logger.info(f"Created new PositionGroup {new_position_group.id} and submitted {len(orders_to_submit)} DCA orders.")

        await self.update_risk_timer(new_position_group.id, risk_config, session=session)
        await self.update_position_stats(new_position_group.id, session=session)

        # Broadcast initial entry signal to Telegram
        await broadcast_entry_signal(new_position_group, new_pyramid, session)

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

        # Dynamically get exchange connector
        exchange_connector = self._get_exchange_connector_for_user(user, signal.exchange)

        # 2. Fetch precision rules
        precision_rules = await exchange_connector.get_precision_rules()
        symbol_precision = precision_rules.get(signal.symbol, {})

        # 3. Calculate DCA levels for this NEW pyramid
        # The new pyramid will have index = current_count + 1 (since current_count is not yet incremented)
        next_pyramid_index = existing_position_group.pyramid_count + 1
        dca_levels = self.grid_calculator_service.calculate_dca_levels(
            base_price=signal.entry_price,
            dca_config=dca_grid_config,
            side=signal.side,
            precision_rules=symbol_precision,
            pyramid_index=next_pyramid_index
        )
        dca_levels = self.grid_calculator_service.calculate_order_quantities(
            dca_levels=dca_levels,
            total_capital_usd=total_capital_usd,
            precision_rules=symbol_precision
        )

        # 4. Update PositionGroup Stats (atomic increment to prevent race conditions)
        pg_repo = self.position_group_repository_class(session)
        new_pyramid_count = await pg_repo.increment_pyramid_count(
            group_id=existing_position_group.id,
            additional_dca_legs=len(dca_levels)
        )
        # Refresh the local object to reflect DB changes
        await session.refresh(existing_position_group)
        
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
        await self.update_position_stats(existing_position_group.id, session=session)

        # Broadcast entry signal to Telegram for the new pyramid
        await broadcast_entry_signal(existing_position_group, new_pyramid, session)

        return existing_position_group

    async def handle_exit_signal(
        self,
        position_group_id: uuid.UUID,
        session: Optional[AsyncSession] = None,
        max_slippage_percent: float = 1.0,
        slippage_action: str = "warn"
    ):
        """
        Handles an exit signal for a position group.
        1. Cancels all open DCA orders.
        2. Places a market order to close the total filled quantity.

        Args:
            position_group_id: ID of the position group to close
            session: Optional database session
            max_slippage_percent: Maximum acceptable slippage (default 1%)
            slippage_action: "warn" to log only, "reject" to raise error
        """
        if session:
            await self._execute_handle_exit_signal(
                position_group_id, session, max_slippage_percent, slippage_action
            )
        else:
            async with self.session_factory() as new_session:
                await self._execute_handle_exit_signal(
                    position_group_id, new_session, max_slippage_percent, slippage_action
                )
                await new_session.commit()

    async def _execute_handle_exit_signal(
        self,
        position_group_id: uuid.UUID,
        session: AsyncSession,
        max_slippage_percent: float = 1.0,
        slippage_action: str = "warn"
    ):
        """
        Core logic for handling an exit signal within a provided session.
        """
        # Re-fetch position group with orders attached in this session
        position_group_repo = self.position_group_repository_class(session)
        position_group = await position_group_repo.get_with_orders(position_group_id)

        if not position_group:
            logger.error(f"PositionGroup {position_group_id} not found for exit signal.")
            return

        # Check if already closed or closing
        if position_group.status == PositionGroupStatus.CLOSED:
            logger.warning(f"PositionGroup {position_group_id} is already closed. Skipping exit signal.")
            return

        # Transition to CLOSING status first
        if position_group.status != PositionGroupStatus.CLOSING:
            position_group.status = PositionGroupStatus.CLOSING
            await position_group_repo.update(position_group)
            await session.flush()
            logger.info(f"PositionGroup {position_group_id} status changed to CLOSING")

        exchange_connector = self._get_exchange_connector_for_user(self.user, position_group.exchange)
        try:
            order_service = self.order_service_class(session=session, user=self.user, exchange_connector=exchange_connector)

            # 1. Cancel open orders
            await order_service.cancel_open_orders_for_group(position_group.id)
            logger.info(f"Cancelled open orders for PositionGroup {position_group.id}")

            # 2. Use the already calculated net total filled quantity
            total_filled_quantity = position_group.total_filled_quantity

            if total_filled_quantity > 0:
                # 3. Close the position with slippage protection
                # Get current price before placing order for slippage calculation
                current_price = Decimal(str(await exchange_connector.get_current_price(position_group.symbol)))

                try:
                    await order_service.close_position_market(
                        position_group=position_group,
                        quantity_to_close=total_filled_quantity,
                        expected_price=current_price,
                        max_slippage_percent=max_slippage_percent,
                        slippage_action=slippage_action
                    )
                    logger.info(f"Placed market order to close {total_filled_quantity} for PositionGroup {position_group.id}")

                    # If successful, update position status and PnL
                    position_group.status = PositionGroupStatus.CLOSED
                    
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
                    logger.info(f"PositionGroup {position_group.id} closed. Realized PnL: {realized_pnl}")

                    # Broadcast exit signal to Telegram
                    await broadcast_exit_signal(position_group, current_price, session)

                except Exception as e:
                    logger.error(f"DEBUG: Caught exception in handle_exit_signal: {type(e)} - {e}")
                    error_msg = str(e).lower()
                    if "insufficient" in error_msg:
                        logger.warning(f"Insufficient funds to close {total_filled_quantity} for Group {position_group.id}. Attempting to close max available balance.")
                        
                        try:
                            # Heuristic to find base currency (remove Quote currency)
                            symbol = position_group.symbol
                            base_currency = symbol
                            for quote in ["USDT", "USDC", "BUSD", "USD", "EUR", "DAI"]:
                                if symbol.endswith(quote):
                                    base_currency = symbol[:-len(quote)]
                                    break
                            
                            # Fetch balance
                            balance_data = await exchange_connector.fetch_free_balance()
                            
                            available_balance = Decimal(str(balance_data.get(base_currency, 0)))
                            
                            if available_balance > 0:
                                logger.info(f"Retrying close with available balance: {available_balance} {base_currency}")
                                await order_service.close_position_market(
                                    position_group=position_group,
                                    quantity_to_close=available_balance
                                )
                                # If retry is successful, update status and commit
                                position_group.status = PositionGroupStatus.CLOSED
                                current_price = Decimal(str(await exchange_connector.get_current_price(position_group.symbol)))
                                exit_value = available_balance * current_price
                                cost_basis = position_group.total_invested_usd # Assuming same initial cost
                                
                                if position_group.side == "long":
                                    realized_pnl = exit_value - cost_basis
                                else:
                                    realized_pnl = cost_basis - exit_value
                                    
                                position_group.realized_pnl_usd = realized_pnl
                                position_group.unrealized_pnl_usd = Decimal("0")
                                position_group.closed_at = datetime.utcnow()
                                await position_group_repo.update(position_group)
                                logger.info(f"PositionGroup {position_group.id} closed after retry. Realized PnL: {realized_pnl}")

                                # Broadcast exit signal to Telegram
                                await broadcast_exit_signal(position_group, current_price, session)

                            else:
                                logger.error(f"No balance found for {base_currency}. Cannot retry close.")
                                raise e # Re-raise original exception if retry not possible
                        except Exception as retry_e:
                            logger.info(f"DEBUG: Free Balance Data: {balance_data}")
                            logger.error(f"Retry close failed: {retry_e}")
                            raise e # Raise original or retry error
                    else:
                        raise e
            else:
                logger.info(f"No filled quantity to close for PositionGroup {position_group.id}. Closing group.")
                position_group.status = PositionGroupStatus.CLOSED
                position_group.closed_at = datetime.utcnow()
                await position_group_repo.update(position_group)
        finally:
            await exchange_connector.close()


    async def update_risk_timer(self, position_group_id: uuid.UUID, risk_config: RiskEngineConfig, session: AsyncSession = None, position_group: Optional[PositionGroup] = None):
        if session:
            await self._execute_update_risk_timer(session, position_group_id, risk_config, position_group)
        else:
            async with self.session_factory() as new_session:
                await self._execute_update_risk_timer(new_session, position_group_id, risk_config, position_group)
                await new_session.commit()

    async def _execute_update_risk_timer(self, session: AsyncSession, position_group_id: uuid.UUID, risk_config: RiskEngineConfig, position_group: Optional[PositionGroup] = None):
        position_group_repo = self.position_group_repository_class(session)
        if not position_group:
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
        elif risk_config.timer_start_condition == "after_all_dca_submitted":
            # Check if all DCA orders have been submitted to the exchange
            # An order is submitted when it has a submitted_at timestamp (status is no longer PENDING/TRIGGER_PENDING)
            from app.repositories.dca_order import DCAOrderRepository
            dca_order_repo = DCAOrderRepository(session)
            all_orders = await dca_order_repo.get_all_orders_by_group_id(str(position_group.id))
            submitted_count = sum(1 for order in all_orders if order.submitted_at is not None)
            if submitted_count >= position_group.total_dca_legs:
                timer_started = True
        elif risk_config.timer_start_condition == "after_all_dca_filled" and position_group.filled_dca_legs == position_group.total_dca_legs:
            timer_started = True

        if timer_started:
            expires_at = datetime.utcnow() + timedelta(minutes=risk_config.post_full_wait_minutes)
            position_group.risk_timer_expires = expires_at
            await position_group_repo.update(position_group)
            # await session.commit() -> handled by caller or wrapper
            logger.info(f"Risk timer started for PositionGroup {position_group.id}. Expires at {expires_at}")


    async def update_position_stats(self, group_id: uuid.UUID, session: AsyncSession = None) -> Optional[PositionGroup]:
        """
        Recalculates total filled quantity and weighted average entry price for a position group.
        """
        if session:
            return await self._execute_update_position_stats(session, group_id)
        else:
            async with self.session_factory() as new_session:
                position_group = await self._execute_update_position_stats(new_session, group_id)
                await new_session.commit() # Commit here when a new session is created
                return position_group

    async def _execute_update_position_stats(self, session: AsyncSession, group_id: uuid.UUID) -> Optional[PositionGroup]:
        position_group_repo = self.position_group_repository_class(session)
        position_group = await position_group_repo.get_with_orders(group_id, refresh=True) # Use get_with_orders with refresh
        if not position_group:
            logger.error(f"PositionGroup {group_id} not found for stats update.")
            return None

        all_orders = list(position_group.dca_orders)
        
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

                # Update Telegram message with filled pyramid data
                await broadcast_entry_signal(position_group, pyramid, session)

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
        
        # Calculate Unrealized PnL - need to get exchange connector here
        # Get user from session to create exchange connector
        user = await session.get(User, position_group.user_id)
        if not user:
            logger.error(f"User {position_group.user_id} not found for position stats update.")
            return
        
        exchange_connector = self._get_exchange_connector_for_user(user, position_group.exchange)
        
        try:
            current_price = await exchange_connector.get_current_price(position_group.symbol)
            current_price = Decimal(str(current_price)) # Cast to Decimal
            
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
            # Count only ENTRY legs that are filled to track grid progress, excluding special TP fill records
            filled_entry_legs = sum(1 for o in filled_orders if o.leg_index != 999 and not o.tp_hit)
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
                            user=user,
                            exchange_connector=exchange_connector
                        )
                        
                        # 1. Cancel all open orders (remove Limit TPs)
                        await order_service.cancel_open_orders_for_group(group_id)
                        
                        # 2. Execute Market Close for remaining quantity
                        close_side = "SELL" if position_group.side.lower() == "long" else "BUY"
                        await order_service.place_market_order(
                            user_id=user.id,
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
        finally:
            # Always close the exchange connector
            await exchange_connector.close()
        
        return position_group