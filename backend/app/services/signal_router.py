from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.webhook_payloads import WebhookPayload
from app.models.user import User
from app.services.queue_manager import QueueManagerService
from app.services.position_manager import PositionManagerService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.grid_calculator import GridCalculatorService
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from decimal import Decimal
from app.services.order_management import OrderService
from app.services.risk_engine import RiskEngineService
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository

class SignalRouterService:
    """
    Service for routing a validated signal for a specific user.
    """
    def __init__(self, user: User):
        self.user = user

    async def route(self, signal: WebhookPayload, db_session: AsyncSession) -> str:
        """
        Routes the signal.
        """
        # Load configurations from the user object
        # The user object is already attached to the session or passed in.
        # Since self.user is a detached object or from a different session context (dependency injection),
        # we should ensure we have the latest data if needed, but here we assume self.user has the configs.
        
        # Parse the JSON stored in the DB into Pydantic models
        try:
            risk_engine_config = RiskEngineConfig.model_validate(self.user.risk_config)
        except Exception as e:
            # Fallback to default if validation fails or field is missing
            risk_engine_config = RiskEngineConfig()

        try:
            # dca_grid_config in DB is stored as the list of levels or the full object?
            # The default in User model is DCAGridConfig([]).model_dump(mode='json'), which is {'root': []} or just [] depending on model.
            # Let's assume it matches the Pydantic model structure.
            dca_grid_config = DCAGridConfig.model_validate(self.user.dca_grid_config)
        except Exception as e:
            # Fallback
            dca_grid_config = DCAGridConfig.model_validate([
                {"gap_percent": 0.0, "weight_percent": 20, "tp_percent": 1.0},
                {"gap_percent": -0.5, "weight_percent": 20, "tp_percent": 0.5},
                {"gap_percent": -1.0, "weight_percent": 20, "tp_percent": 0.5},
                {"gap_percent": -2.0, "weight_percent": 20, "tp_percent": 0.5},
                {"gap_percent": -4.0, "weight_percent": 20, "tp_percent": 0.5}
            ])

        # TODO: Fetch this from user settings or config
        total_capital_usd = Decimal("10000")

        exchange_connector = get_exchange_connector(signal.tv.exchange.lower())
        grid_calculator_service = GridCalculatorService()

        execution_pool_manager = ExecutionPoolManager(
            session_factory=lambda: db_session, # Changed to session_factory
            position_group_repository_class=PositionGroupRepository
        )

        position_manager_service = PositionManagerService(
            session_factory=lambda: db_session, # Changed to session_factory
            user=self.user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=grid_calculator_service,
            order_service_class=OrderService,
            exchange_connector=exchange_connector
        )

        risk_engine_service = RiskEngineService(
            session_factory=lambda: db_session,
            position_group_repository_class=PositionGroupRepository,
            risk_action_repository_class=RiskActionRepository,
            dca_order_repository_class=DCAOrderRepository,
            exchange_connector=exchange_connector,
            order_service_class=OrderService,
            risk_engine_config=risk_engine_config
        )

        queue_manager_service = QueueManagerService(
            session_factory=lambda: db_session, # Changed to session_factory
            user=self.user,
            queued_signal_repository_class=QueuedSignalRepository,
            position_group_repository_class=PositionGroupRepository,
            exchange_connector=exchange_connector,
            execution_pool_manager=execution_pool_manager,
            position_manager_service=position_manager_service,
            risk_engine_service=risk_engine_service,
            grid_calculator_service=grid_calculator_service,
            order_service_class=OrderService,
            risk_engine_config=risk_engine_config,
            dca_grid_config=dca_grid_config,
            total_capital_usd=total_capital_usd
        )

        # Handle Exit Signals
        if signal.execution_intent.side in ["flat", "exit"]:
             # Remove any pending entry signal for this symbol
             # We map "flat" or "exit" to null side or handle generic removal
             # If the signal has a specific side (e.g. "exit long"), we could be specific.
             # But usually "flat" means close everything.
             # For now, remove any signal for this symbol/timeframe.
             await queue_manager_service.remove_signal_for_symbol_and_timeframe(
                 symbol=signal.tv.symbol, 
                 timeframe=signal.tv.timeframe
             )
             
             # Also trigger position close if active (handled by separate logic usually, 
             # but we can check if we need to forward this to position manager)
             # For this specific task (Queue Purging), we are done.
             return f"Exit signal received for {signal.tv.symbol}. Queue purged."

        # This is a simplified routing logic. The actual implementation will be more complex.
        await queue_manager_service.add_signal_to_queue(signal)

        return f"Signal for {signal.tv.symbol} for user {self.user.username} has been queued."