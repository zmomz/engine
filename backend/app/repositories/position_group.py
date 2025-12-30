from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, date
import uuid
from decimal import Decimal

from app.models import PositionGroup, Pyramid
from app.repositories.base import BaseRepository


class PositionGroupRepository(BaseRepository[PositionGroup]):
    def __init__(self, session: AsyncSession):
        super().__init__(PositionGroup, session)

    async def get_by_symbol(self, user_id: uuid.UUID, symbol: str) -> list[PositionGroup]:
        """
        Retrieves all position groups for a given user and symbol.

        SECURITY: user_id is required to prevent cross-user data access.
        """
        result = await self.session.execute(
            select(self.model).where(
                self.model.user_id == user_id,
                self.model.symbol == symbol
            )
        )
        return result.scalars().all()

    async def get_with_orders(self, group_id: uuid.UUID, refresh: bool = False) -> PositionGroup | None:
        """
        Retrieves a position group by ID, eagerly loading its DCA orders and pyramids.
        """
        query = (
            select(self.model)
            .where(self.model.id == group_id)
            .options(
                selectinload(self.model.dca_orders),
                selectinload(self.model.pyramids).selectinload(Pyramid.dca_orders)
            )
        )
        if refresh:
            query = query.execution_options(populate_existing=True)

        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_active_position_groups(self, user_id: uuid.UUID, for_update: bool = False) -> list[PositionGroup]:
        """
        Retrieves all active position groups for a specific user.

        SECURITY: user_id is now required to prevent cross-user data access.
        Use get_active_position_groups_for_user for full status set (live, partially_filled, active, closing).
        """
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == "active"
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_position_groups_for_user(self, user_id: uuid.UUID, for_update: bool = False) -> list[PositionGroup]:
        """
        Retrieves all active position groups for a given user.
        """
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status.in_(["live", "partially_filled", "active", "closing"])
        ).options(
            selectinload(self.model.pyramids).selectinload(Pyramid.dca_orders)
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_position_group_for_signal(
        self,
        user_id: uuid.UUID,
        symbol: str,
        exchange: str,
        timeframe: int,
        side: str,
        for_update: bool = True
    ) -> PositionGroup | None:
        """
        Retrieves a specific active position group matching the signal parameters.
        Uses SQL WHERE clause for efficient filtering and optional row locking.

        Args:
            user_id: The user's ID
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            exchange: Exchange name (e.g., 'binance')
            timeframe: Timeframe in minutes
            side: Position side ('long' or 'short')
            for_update: Whether to acquire a row lock (default True for race condition prevention)
        """
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.symbol == symbol,
            self.model.exchange == exchange,
            self.model.timeframe == timeframe,
            self.model.side == side,
            self.model.status.in_(["live", "partially_filled", "active", "closing"])
        ).options(
            selectinload(self.model.pyramids).selectinload(Pyramid.dca_orders)
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_active_position_group_for_exit(
        self,
        user_id: uuid.UUID,
        symbol: str,
        exchange: str,
        side: str,
        timeframe: int | None = None,
        for_update: bool = True
    ) -> PositionGroup | None:
        """
        Retrieves an active position group for exit signal.
        Matches on timeframe if provided, otherwise matches any timeframe.

        Args:
            user_id: The user's ID
            symbol: Trading pair symbol
            exchange: Exchange name
            side: Position side to close ('long' or 'short')
            timeframe: Optional timeframe filter (if None, matches any)
            for_update: Whether to acquire a row lock
        """
        conditions = [
            self.model.user_id == user_id,
            self.model.symbol == symbol,
            self.model.exchange == exchange,
            self.model.side == side,
            self.model.status.in_(["live", "partially_filled", "active", "closing"])
        ]
        if timeframe is not None:
            conditions.append(self.model.timeframe == timeframe)

        query = select(self.model).where(*conditions).options(
            selectinload(self.model.pyramids).selectinload(Pyramid.dca_orders)
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_all_active_by_user(self, user_id: uuid.UUID) -> list[PositionGroup]:
        """
        Retrieves all open position groups for a given user.
        Includes positions in live, partially_filled, and active states.
        Excludes positions that are closing, closed, failed, or waiting.
        """
        open_statuses = ("live", "partially_filled", "active")
        result = await self.session.execute(
            select(self.model).where(
                self.model.user_id == user_id,
                self.model.status.in_(open_statuses)
            )
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

    async def get_closed_by_user(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[list[PositionGroup], int]:
        """
        Retrieves closed position groups for a given user with pagination.

        Args:
            user_id: The user's ID
            limit: Maximum number of records to return (default 100, max 500)
            offset: Number of records to skip (default 0)

        Returns:
            Tuple of (list of PositionGroups, total count)
        """
        # Clamp limit to prevent excessive queries
        limit = min(max(1, limit), 500)
        offset = max(0, offset)

        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(self.model)
            .where(self.model.user_id == user_id, self.model.status == "closed")
        )
        total_count = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            select(self.model)
            .where(self.model.user_id == user_id, self.model.status == "closed")
            .order_by(self.model.closed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all(), total_count

    async def get_closed_by_user_all(self, user_id: uuid.UUID) -> list[PositionGroup]:
        """
        Retrieves all closed position groups for a given user, ordered by closed_at descending.
        DEPRECATED: Use get_closed_by_user with pagination for better performance.
        """
        result = await self.session.execute(
            select(self.model)
            .where(self.model.user_id == user_id, self.model.status == "closed")
            .order_by(self.model.closed_at.desc())
        )
        return result.scalars().all()

    async def increment_pyramid_count(
        self,
        group_id: uuid.UUID,
        additional_dca_legs: int = 0
    ) -> int:
        """
        Atomically increments pyramid_count using SQL expression.
        Returns the new pyramid_count value.

        This is safer than Python-side increment when row locking may not be in place.

        Note: replacement_count is NOT incremented here. It should only be incremented
        when a queued signal replaces another (tracked in QueuedSignal.replacement_count
        and optionally synced to PositionGroup when the signal is promoted).

        Args:
            group_id: The position group ID
            additional_dca_legs: Number of new DCA legs to add to total_dca_legs
        """
        stmt = (
            update(self.model)
            .where(self.model.id == group_id)
            .values(
                pyramid_count=self.model.pyramid_count + 1,
                total_dca_legs=self.model.total_dca_legs + additional_dca_legs
            )
            .returning(self.model.pyramid_count)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

