from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, date
import uuid
from decimal import Decimal

from app.models import PositionGroup
from app.repositories.base import BaseRepository


class PositionGroupRepository(BaseRepository[PositionGroup]):
    def __init__(self, session: AsyncSession):
        super().__init__(PositionGroup, session)

    async def get_by_symbol(self, symbol: str) -> list[PositionGroup]:
        """
        Retrieves all position groups for a given symbol.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.symbol == symbol)
        )
        return result.scalars().all()

    async def get_active_position_groups(self, for_update: bool = False) -> list[PositionGroup]:
        """
        Retrieves all position groups with status 'active'.
        """
        return await self.get_by_status(["active"], for_update=for_update)

    async def get_active_position_groups_for_user(self, user_id: uuid.UUID, for_update: bool = False) -> list[PositionGroup]:
        """
        Retrieves all active position groups for a given user.
        """
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status.in_(["live", "partially_filled", "active", "closing"])
        ).options(
            selectinload(self.model.pyramids).selectinload(self.model.pyramids.property.mapper.class_.dca_orders)
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_active_by_user(self, user_id: uuid.UUID) -> list[PositionGroup]:
        """
        Retrieves all active position groups for a given user.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.user_id == user_id, self.model.status == "active")
        )
        return result.scalars().all()

    async def get_by_user_and_id(self, user_id: uuid.UUID, group_id: uuid.UUID) -> PositionGroup | None:
        """
        Retrieves a specific position group for a given user and group ID.
        """
        result = await self.session.execute(
            select(self.model).where(self.model.user_id == user_id, self.model.id == group_id)
        )
        return result.scalars().first()

    async def get_daily_realized_pnl(self, user_id: uuid.UUID, query_date: date = None) -> Decimal:
        """
        Calculates the total realized PnL for a user on a specific date (UTC).
        Defaults to current UTC date if not provided.
        """
        if query_date is None:
            query_date = datetime.utcnow().date()
        
        start_of_day = datetime.combine(query_date, datetime.min.time())
        end_of_day = datetime.combine(query_date, datetime.max.time())

        result = await self.session.execute(
            select(func.sum(self.model.realized_pnl_usd))
            .where(
                self.model.user_id == user_id,
                self.model.closed_at >= start_of_day,
                self.model.closed_at <= end_of_day
            )
        )
        total_pnl = result.scalar()
        return total_pnl if total_pnl is not None else Decimal("0")

    async def get_total_pnl_for_user(self, user_id: uuid.UUID) -> Decimal:
        """
        Calculates the total PnL (realized + unrealized) for a user.
        """
        result = await self.session.execute(
            select(
                func.sum(self.model.realized_pnl_usd) + func.sum(self.model.unrealized_pnl_usd)
            ).where(self.model.user_id == user_id)
        )
        total_pnl = result.scalar()
        return total_pnl if total_pnl is not None else Decimal("0")

    async def get_total_realized_pnl_only(self, user_id: uuid.UUID) -> Decimal:
        """
        Calculates the total realized PnL for a user (ignoring unrealized).
        """
        result = await self.session.execute(
            select(
                func.sum(self.model.realized_pnl_usd)
            ).where(self.model.user_id == user_id)
        )
        total_pnl = result.scalar()
        return total_pnl if total_pnl is not None else Decimal("0")

    async def get_closed_by_user(self, user_id: uuid.UUID) -> list[PositionGroup]:
        """
        Retrieves all closed position groups for a given user, ordered by closed_at descending.
        """
        result = await self.session.execute(
            select(self.model)
            .where(self.model.user_id == user_id, self.model.status == "closed")
            .order_by(self.model.closed_at.desc())
        )
        return result.scalars().all()
