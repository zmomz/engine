"""
Service for the Risk Engine, responsible for identifying and offsetting losing positions.
"""
import asyncio
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.risk_action import RiskAction, RiskActionType
from app.models.queued_signal import QueuedSignal
from app.models.user import User # Added import
from app.repositories.user import UserRepository # Added import
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.factory import get_exchange_connector # Added import
from app.services.order_management import OrderService
from app.schemas.grid_config import RiskEngineConfig # Assuming this schema exists
from app.core.security import EncryptionService # Added import
from fastapi import HTTPException, status # Added imports

logger = logging.getLogger(__name__)

# Helper function (will be moved to precision service later)
def round_to_step_size(value: Decimal, step_size: Decimal) -> Decimal:
    return (value / step_size).quantize(Decimal('1')) * step_size

# --- Standalone functions for selection logic (as per EP.md 6.2) ---

def _filter_eligible_losers(position_groups: List[PositionGroup], config: RiskEngineConfig) -> List[PositionGroup]:
    """Helper to filter positions eligible for loss offset."""
    eligible_losers = []
    for pg in position_groups:
        # Must meet all conditions
        if not all([
            pg.status == PositionGroupStatus.ACTIVE.value,
            pg.pyramid_count >= pg.max_pyramids if config.require_full_pyramids else True,
            pg.risk_timer_expires and pg.risk_timer_expires <= datetime.utcnow(),
            pg.unrealized_pnl_percent <= config.loss_threshold_percent,
            not pg.risk_blocked,
            not pg.risk_skip_once
        ]):
            continue
        
        # Age filter (optional)
        if config.use_trade_age_filter:
            age_minutes = (datetime.utcnow() - pg.created_at).total_seconds() / 60
            if age_minutes < config.age_threshold_minutes:
                continue
        
        eligible_losers.append(pg)
    return eligible_losers

def _select_top_winners(position_groups: List[PositionGroup], count: int) -> List[PositionGroup]:
    """Helper to select top profitable positions."""
    winning_positions = [
        pg for pg in position_groups
        if pg.status == PositionGroupStatus.ACTIVE.value and pg.unrealized_pnl_usd > 0
    ]
    
    # Sort by USD profit (descending)
    winning_positions.sort(
        key=lambda pg: pg.unrealized_pnl_usd,
        reverse=True
    )
    
    # Take up to max_winners_to_combine
    return winning_positions[:count]

def select_loser_and_winners(
    position_groups: List[PositionGroup],
    config: RiskEngineConfig
) -> Tuple[Optional[PositionGroup], List[PositionGroup], Decimal]:
    """
    Risk Engine selection logic (SoW Section 4.4 & 4.5):
    
    Loser Selection (by % loss):
    1. Highest loss percentage
    2. If tied → highest unrealized loss USD
    3. If tied → oldest trade
    
    Winner Selection (by $ profit):
    - Rank all winning positions by unrealized profit USD
    - Select up to max_winners_to_combine (default: 3)
    
    Offset Execution:
    - Calculate required_usd to cover loser
    - Close winners partially to realize that amount
    """
    
    eligible_losers = _filter_eligible_losers(position_groups, config)
    
    if not eligible_losers:
        return None, [], Decimal("0")
    
    # Sort losers by priority
    selected_loser = max(eligible_losers, key=lambda pg: (
        abs(pg.unrealized_pnl_percent),  # Primary: highest loss %
        abs(pg.unrealized_pnl_usd),      # Secondary: highest loss $
        -pg.created_at.timestamp()        # Tertiary: oldest
    ))
    
    required_usd = abs(selected_loser.unrealized_pnl_usd)
    
    selected_winners = _select_top_winners(position_groups, config.max_winners_to_combine)
    
    return selected_loser, selected_winners, required_usd

async def calculate_partial_close_quantities(
    exchange_connector: ExchangeInterface,
    winners: List[PositionGroup],
    required_usd: Decimal,
    precision_rules: Dict
) -> List[Tuple[PositionGroup, Decimal]]:
    """
    Calculate how much to close from each winner to realize required_usd.
    
    Returns: List of (PositionGroup, quantity_to_close)
    """
    close_plan = []
    remaining_needed = required_usd
    
    for winner in winners:
        if remaining_needed <= 0:
            break
        
        # Calculate how much profit this winner can contribute
        available_profit = winner.unrealized_pnl_usd
        
        # Determine how much of this winner to close
        profit_to_take = min(available_profit, remaining_needed)
        
        # Calculate quantity to close to realize this profit
        current_price = await exchange_connector.get_current_price(winner.symbol)
        profit_per_unit = current_price - winner.weighted_avg_entry
        if winner.side == "short":
            profit_per_unit = winner.weighted_avg_entry - current_price
        
        if profit_per_unit <= 0:
            logger.warning(f"Cannot calculate quantity for {winner.symbol}: profit_per_unit is zero or negative.")
            continue

        quantity_to_close = profit_to_take / profit_per_unit
        
        # Round to step size
        symbol_precision = precision_rules.get(winner.symbol, {})
        step_size = symbol_precision.get("step_size", Decimal("0.001")) # Default if not found
        quantity_to_close = round_to_step_size(quantity_to_close, step_size)
        
        # Check minimum notional
        notional_value = quantity_to_close * current_price
        min_notional = symbol_precision.get("min_notional", Decimal("10")) # Default if not found
        
        if notional_value < min_notional:
            logger.warning(
                f"Partial close for {winner.symbol} below min notional "
                f"({notional_value} < {min_notional}). Skipping."
            )
            continue

        # Cap at available quantity
        if quantity_to_close > winner.total_filled_quantity:
            quantity_to_close = winner.total_filled_quantity
        
        close_plan.append((winner, quantity_to_close))
        remaining_needed -= profit_to_take
    
    return close_plan

class RiskEngineService:
    def __init__(
        self,
        session_factory: callable,
        position_group_repository_class: type[PositionGroupRepository],
        risk_action_repository_class: type[RiskActionRepository],
        dca_order_repository_class: type[DCAOrderRepository],
        exchange_connector: ExchangeInterface,
        order_service_class: type[OrderService],
        risk_engine_config: RiskEngineConfig,
        polling_interval_seconds: int = 60,
        user: Optional[User] = None
    ):
        self.session_factory = session_factory
        self.position_group_repository_class = position_group_repository_class
        self.risk_action_repository_class = risk_action_repository_class
        self.dca_order_repository_class = dca_order_repository_class
        self.exchange_connector = exchange_connector
        self.order_service_class = order_service_class
        self.polling_interval_seconds = polling_interval_seconds
        self.config = risk_engine_config
        self.user = user
        self._running = False
        self._monitor_task = None

    async def validate_pre_trade_risk(
        self,
        signal: QueuedSignal,
        active_positions: List[PositionGroup],
        allocated_capital_usd: Decimal,
        session: AsyncSession,
        is_pyramid_continuation: bool = False
    ) -> bool:
        """
        Performs pre-trade risk checks before promoting a signal.
        """
        # 0. Max Open Positions Global
        # If it's a pyramid continuation, we are adding to an existing group, so we don't count against "new" positions
        if not is_pyramid_continuation:
            active_groups_count = len(active_positions)
            if active_groups_count >= self.config.max_open_positions_global:
                logger.info(f"Risk Check Failed: Max global positions reached ({active_groups_count}/{self.config.max_open_positions_global})")
                return False

        # 1. Max Open Positions Per Symbol
        # If it's a pyramid continuation, we are adding to an existing group, so we don't count against "new" positions per symbol
        if not is_pyramid_continuation:
            symbol_positions = [p for p in active_positions if p.symbol == signal.symbol]
            if len(symbol_positions) >= self.config.max_open_positions_per_symbol:
                logger.info(f"Risk Check Failed: Max positions for {signal.symbol} reached ({len(symbol_positions)}/{self.config.max_open_positions_per_symbol})")
                return False

        # 2. Max Total Exposure
        current_exposure = sum(p.total_invested_usd for p in active_positions)
        if (current_exposure + allocated_capital_usd) > self.config.max_total_exposure_usd:
             logger.info(f"Risk Check Failed: Max exposure reached ({current_exposure + allocated_capital_usd} > {self.config.max_total_exposure_usd})")
             return False

        # 3. Daily Loss Limit (Circuit Breaker)
        position_group_repo = self.position_group_repository_class(session)
        daily_pnl = await position_group_repo.get_daily_realized_pnl(user_id=signal.user_id)
        
        # If daily_pnl is negative and its absolute value exceeds max_daily_loss_usd
        if daily_pnl < 0 and abs(daily_pnl) >= self.config.max_daily_loss_usd:
             logger.info(f"Risk Check Failed: Daily loss limit reached ({daily_pnl} USD). Max loss allowed: {self.config.max_daily_loss_usd}")
             return False
        
        return True

    async def _evaluate_positions(self):
        """
        Evaluates all active positions for risk management and initiates offset if conditions are met.
        Iterates through all active users to ensure isolation.
        """
        async for session in self.session_factory():
            try:
                user_repo = UserRepository(session)
                active_users = await user_repo.get_all_active_users()

                for user in active_users:
                    try:
                        await self._evaluate_user_positions(session, user)
                    except Exception as e:
                        logger.error(f"Risk Engine: Error processing user {user.id}: {e}")
            except Exception as e:
                logger.error(f"Risk Engine: Critical error in evaluation loop: {e}")

    async def _evaluate_user_positions(self, session, user):
        """
        Evaluates positions for a single user.
        """
        try:
            position_group_repo = self.position_group_repository_class(session)
            risk_action_repo = self.risk_action_repository_class(session)
            
            # 1. Get User Positions
            all_positions = await position_group_repo.get_all_active_by_user(user.id)
            
            # 2. Determine Risk Config (User > Global)
            config = self.config
            if user.risk_config:
                try:
                    if isinstance(user.risk_config, dict):
                        config = RiskEngineConfig(**user.risk_config)
                except Exception as e:
                    logger.warning(f"Risk Engine: Invalid config for user {user.id}, using default. Error: {e}")

            # 3. Select Loser and Winners
            loser, winners, required_usd = select_loser_and_winners(all_positions, config)

            if loser and winners:
                logger.info(f"Risk Engine: Identified loser {loser.symbol} for user {user.id} (loss: {loser.unrealized_pnl_usd} USD) and {len(winners)} winners.")
                
                # Decrypt keys and get exchange connector
                encryption_service = EncryptionService()
                try:
                    # Fix for multi-key: Use loser.exchange
                    encrypted_data = user.encrypted_api_keys
                    target_exchange = loser.exchange
                    if isinstance(encrypted_data, dict):
                         if target_exchange in encrypted_data:
                             encrypted_data = encrypted_data[target_exchange]
                         elif "encrypted_data" not in encrypted_data:
                             logger.error(f"Risk Engine: Keys for {target_exchange} not found for user {user.id}.")
                             return

                    api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
                    exchange_connector = get_exchange_connector(
                        exchange_type=loser.exchange,
                        api_key=api_key,
                        secret_key=secret_key
                    )
                except Exception as e:
                        logger.error(f"Risk Engine: Failed to initialize exchange connector for user {user.id}: {e}")
                        return

                # Instantiate OrderService
                order_service = self.order_service_class(
                    session=session,
                    user=user,
                    exchange_connector=exchange_connector
                )

                # Get Precision Rules
                try:
                    full_precision_rules = await exchange_connector.get_precision_rules()
                except Exception as e:
                    logger.error(f"Risk Engine: Failed to fetch precision rules for user {user.id}: {e}")
                    return
                
                close_plan = await calculate_partial_close_quantities(exchange_connector, winners, required_usd, full_precision_rules)

                if not close_plan and required_usd > 0:
                    logger.warning(f"Risk Engine: No winners could be partially closed for loser {loser.symbol}. Skipping offset.")
                    return

                # Close the loser
                await order_service.place_market_order(
                    user_id=loser.user_id,
                    exchange=loser.exchange,
                    symbol=loser.symbol,
                    side="sell" if loser.side == "long" else "buy",
                    quantity=loser.total_filled_quantity,
                    position_group_id=loser.id
                )
                logger.info(f"Risk Engine: Closed loser {loser.symbol} (ID: {loser.id}).")

                winner_details = []
                for winner_pg, quantity_to_close in close_plan:
                    await order_service.place_market_order(
                        user_id=winner_pg.user_id,
                        exchange=winner_pg.exchange,
                        symbol=winner_pg.symbol,
                        side="sell" if winner_pg.side == "long" else "buy",
                        quantity=quantity_to_close,
                        position_group_id=winner_pg.id
                    )
                    logger.info(f"Risk Engine: Partially closed winner {winner_pg.symbol} (ID: {winner_pg.id}) for {quantity_to_close} units.")
                    winner_details.append({
                        "group_id": str(winner_pg.id),
                        "pnl_usd": str(winner_pg.unrealized_pnl_usd),
                        "quantity_closed": str(quantity_to_close)
                    })
                
                risk_action = RiskAction(
                    group_id=loser.id,
                    action_type=RiskActionType.OFFSET_LOSS,
                    loser_group_id=loser.id,
                    loser_pnl_usd=loser.unrealized_pnl_usd,
                    winner_details=winner_details
                )
                await risk_action_repo.create(risk_action)
                await session.commit()
                logger.info(f"Risk Engine: Offset for {loser.symbol} successfully executed and recorded.")
            else:
                logger.debug(f"Risk Engine: No eligible loser or winners found for user {user.id}.")
        except Exception as e:
            logger.error(f"Risk Engine: Error evaluating positions for user {user.id}. Rolling back: {e}")
            await session.rollback()

    async def start_monitoring_task(self):
        """
        Starts the background task for the Risk Engine.
        """
        if not self._running:
            self._running = True
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
            logger.info("RiskEngineService monitoring task started.")

    async def _monitoring_loop(self):
        """
        The main loop for the Risk Engine monitoring task.
        """
        while self._running:
            try:
                await self._evaluate_positions()
                await asyncio.sleep(self.polling_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Risk Engine monitoring loop: {e}")
                await asyncio.sleep(self.polling_interval_seconds) # Wait before retrying

    async def stop_monitoring_task(self):
        """
        Stops the background Risk Engine monitoring task.
        """
        if self._running and self._monitor_task:
            self._running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("RiskEngineService monitoring task stopped.")

    async def set_risk_blocked(self, group_id: uuid.UUID, blocked: bool) -> PositionGroup:
        """Sets the risk_blocked flag for a specific PositionGroup."""
        async for session in self.session_factory():
            position_group_repo = self.position_group_repository_class(session)
            position_group = await position_group_repo.get(group_id)
            if not position_group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PositionGroup not found")
            
            # Security Check
            if self.user and position_group.user_id != self.user.id:
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this position group")

            position_group.risk_blocked = blocked
            await position_group_repo.update(position_group)
            await session.commit()
            await session.refresh(position_group)
            logger.info(f"PositionGroup {group_id} risk_blocked set to {blocked}")
            return position_group

    async def set_risk_skip_once(self, group_id: uuid.UUID, skip: bool) -> PositionGroup:
        """Sets the risk_skip_once flag for a specific PositionGroup."""
        async for session in self.session_factory():
            position_group_repo = self.position_group_repository_class(session)
            position_group = await position_group_repo.get(group_id)
            if not position_group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PositionGroup not found")
            
            # Security Check
            if self.user and position_group.user_id != self.user.id:
                 raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this position group")

            position_group.risk_skip_once = skip
            await position_group_repo.update(position_group)
            await session.commit()
            await session.refresh(position_group)
            return position_group
    
    async def get_current_status(self) -> dict:
        """
        Returns the current state of the risk engine's evaluation without taking action.
        Identifies potential loser and winners based on current positions.
        """
        async for session in self.session_factory():
            position_group_repo = self.position_group_repository_class(session)
            
            if self.user:
                all_positions = await position_group_repo.get_all_active_by_user(self.user.id)
            else:
                all_positions = await position_group_repo.get_all()
            
            loser, winners, required_usd = select_loser_and_winners(all_positions, self.config)
            
            loser_info = None
            if loser:
                loser_info = {
                    "id": str(loser.id),
                    "symbol": loser.symbol,
                    "unrealized_pnl_percent": float(loser.unrealized_pnl_percent),
                    "unrealized_pnl_usd": float(loser.unrealized_pnl_usd),
                    "risk_blocked": loser.risk_blocked,
                    "risk_skip_once": loser.risk_skip_once,
                    "risk_timer_expires": loser.risk_timer_expires.isoformat() if loser.risk_timer_expires else None,
                }
            
            winners_info = []
            for winner in winners:
                winners_info.append({
                    "id": str(winner.id),
                    "symbol": winner.symbol,
                    "unrealized_pnl_usd": float(winner.unrealized_pnl_usd),
                })
            
            return {
                "identified_loser": loser_info,
                "identified_winners": winners_info,
                "required_offset_usd": float(required_usd),
                "risk_engine_running": self._running,
                "config": self.config.model_dump()
            }

    async def run_single_evaluation(self):
        """
        Triggers a single, immediate evaluation run of the risk engine.
        """
        if self.user:
            logger.info(f"Risk Engine: Manually triggered single evaluation for user {self.user.id}.")
            async for session in self.session_factory():
                await self._evaluate_user_positions(session, self.user)
        else:
            logger.info("Risk Engine: Manually triggered single evaluation (Global).")
            await self._evaluate_positions()
        return {"status": "Risk evaluation completed"}