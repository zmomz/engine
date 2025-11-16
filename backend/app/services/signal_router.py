from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.webhook_payloads import TradingViewSignal
from app.models.position_group import PositionGroup
from app.repositories.position_group import PositionGroupRepository
from decimal import Decimal

class SignalRouterService:
    """
    Service for routing a validated signal.
    """
    async def route(self, signal: TradingViewSignal, db_session: AsyncSession) -> str:
        """
        Routes the signal.
        """
        repo = PositionGroupRepository(db_session)
        
        # Basic logic to create a new position group for every signal for now
        # This will be expanded in later phases
        new_group = PositionGroup(
            user_id=signal.user_id,
            exchange="binance", # Placeholder
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=signal.side,
            status="live", # Default status
            total_dca_legs=5, # Placeholder
            base_entry_price=signal.price,
            weighted_avg_entry=signal.price,
            tp_mode="per_leg" # Placeholder
        )
        
        await repo.create(new_group)
        await db_session.commit()
        
        return f"Signal for {signal.symbol} routed and created new position group."
