"""
Tests for PositionGroupRepository - Position group database operations.
"""
import pytest
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.position_group import PositionGroupRepository
from app.models.position_group import PositionGroup


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def position_group_repo(mock_session):
    return PositionGroupRepository(mock_session)


class TestPositionGroupRepositoryInit:
    """Test PositionGroupRepository initialization."""

    def test_init(self, mock_session):
        repo = PositionGroupRepository(mock_session)
        assert repo.session == mock_session
        assert repo.model == PositionGroup


class TestGetBySymbol:
    """Test get_by_symbol method."""

    @pytest.mark.asyncio
    async def test_get_by_symbol(self, position_group_repo, mock_session):
        """Test getting position groups by symbol."""
        user_id = uuid.uuid4()
        mock_groups = [MagicMock(spec=PositionGroup) for _ in range(2)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_by_symbol(user_id, "BTCUSDT")

        assert len(groups) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_symbol_empty(self, position_group_repo, mock_session):
        """Test getting position groups when none exist."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_by_symbol(user_id, "ETHUSDT")

        assert len(groups) == 0


class TestGetWithOrders:
    """Test get_with_orders method."""

    @pytest.mark.asyncio
    async def test_get_with_orders_found(self, position_group_repo, mock_session):
        """Test getting a position group with orders."""
        group_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)
        mock_group.id = group_id

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_with_orders(group_id)

        assert group == mock_group

    @pytest.mark.asyncio
    async def test_get_with_orders_not_found(self, position_group_repo, mock_session):
        """Test getting a position group when not found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_with_orders(uuid.uuid4())

        assert group is None

    @pytest.mark.asyncio
    async def test_get_with_orders_refresh(self, position_group_repo, mock_session):
        """Test getting a position group with refresh option."""
        group_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_with_orders(group_id, refresh=True)

        assert group == mock_group


class TestGetActivePositionGroups:
    """Test get_active_position_groups method."""

    @pytest.mark.asyncio
    async def test_get_active_position_groups(self, position_group_repo, mock_session):
        """Test getting active position groups."""
        user_id = uuid.uuid4()
        mock_groups = [MagicMock(spec=PositionGroup)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_active_position_groups(user_id)

        assert len(groups) == 1

    @pytest.mark.asyncio
    async def test_get_active_position_groups_for_update(self, position_group_repo, mock_session):
        """Test getting active position groups with FOR UPDATE."""
        user_id = uuid.uuid4()
        mock_groups = []

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_active_position_groups(user_id, for_update=True)

        assert len(groups) == 0


class TestGetActivePositionGroupsForUser:
    """Test get_active_position_groups_for_user method."""

    @pytest.mark.asyncio
    async def test_get_active_position_groups_for_user(self, position_group_repo, mock_session):
        """Test getting all active position groups for a user."""
        user_id = uuid.uuid4()
        mock_groups = [MagicMock(spec=PositionGroup) for _ in range(3)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_active_position_groups_for_user(user_id)

        assert len(groups) == 3

    @pytest.mark.asyncio
    async def test_get_active_position_groups_for_user_for_update(self, position_group_repo, mock_session):
        """Test getting active position groups with FOR UPDATE lock."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_active_position_groups_for_user(user_id, for_update=True)

        assert len(groups) == 0


class TestGetActivePositionGroupForSignal:
    """Test get_active_position_group_for_signal method."""

    @pytest.mark.asyncio
    async def test_get_active_position_group_for_signal_found(self, position_group_repo, mock_session):
        """Test getting position group for signal."""
        user_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_active_position_group_for_signal(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=60,
            side="long"
        )

        assert group == mock_group

    @pytest.mark.asyncio
    async def test_get_active_position_group_for_signal_not_found(self, position_group_repo, mock_session):
        """Test getting position group for signal when not found."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_active_position_group_for_signal(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=60,
            side="long"
        )

        assert group is None

    @pytest.mark.asyncio
    async def test_get_active_position_group_for_signal_no_update(self, position_group_repo, mock_session):
        """Test getting position group for signal without FOR UPDATE."""
        user_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_active_position_group_for_signal(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=60,
            side="long",
            for_update=False
        )

        assert group == mock_group


class TestGetActivePositionGroupForExit:
    """Test get_active_position_group_for_exit method."""

    @pytest.mark.asyncio
    async def test_get_active_position_group_for_exit_found(self, position_group_repo, mock_session):
        """Test getting position group for exit."""
        user_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_active_position_group_for_exit(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            side="long"
        )

        assert group == mock_group

    @pytest.mark.asyncio
    async def test_get_active_position_group_for_exit_with_timeframe(self, position_group_repo, mock_session):
        """Test getting position group for exit with timeframe filter."""
        user_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_active_position_group_for_exit(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            side="long",
            timeframe=60
        )

        assert group == mock_group

    @pytest.mark.asyncio
    async def test_get_active_position_group_for_exit_not_found(self, position_group_repo, mock_session):
        """Test getting position group for exit when not found."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_active_position_group_for_exit(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            side="long"
        )

        assert group is None


class TestGetAllActiveByUser:
    """Test get_all_active_by_user method."""

    @pytest.mark.asyncio
    async def test_get_all_active_by_user(self, position_group_repo, mock_session):
        """Test getting all active groups for a user."""
        user_id = uuid.uuid4()
        mock_groups = [MagicMock(spec=PositionGroup) for _ in range(2)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_all_active_by_user(user_id)

        assert len(groups) == 2


class TestGetByUserAndId:
    """Test get_by_user_and_id method."""

    @pytest.mark.asyncio
    async def test_get_by_user_and_id_found(self, position_group_repo, mock_session):
        """Test getting position group by user and id."""
        user_id = uuid.uuid4()
        group_id = uuid.uuid4()
        mock_group = MagicMock(spec=PositionGroup)
        mock_group.id = group_id

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_group
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_by_user_and_id(user_id, group_id)

        assert group == mock_group

    @pytest.mark.asyncio
    async def test_get_by_user_and_id_not_found(self, position_group_repo, mock_session):
        """Test getting position group when not found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        group = await position_group_repo.get_by_user_and_id(uuid.uuid4(), uuid.uuid4())

        assert group is None


class TestGetDailyRealizedPnl:
    """Test get_daily_realized_pnl method."""

    @pytest.mark.asyncio
    async def test_get_daily_realized_pnl(self, position_group_repo, mock_session):
        """Test getting daily realized PnL."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("500.50")
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_daily_realized_pnl(user_id)

        assert pnl == Decimal("500.50")

    @pytest.mark.asyncio
    async def test_get_daily_realized_pnl_specific_date(self, position_group_repo, mock_session):
        """Test getting daily realized PnL for a specific date."""
        user_id = uuid.uuid4()
        query_date = date(2024, 1, 15)

        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("250.00")
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_daily_realized_pnl(user_id, query_date)

        assert pnl == Decimal("250.00")

    @pytest.mark.asyncio
    async def test_get_daily_realized_pnl_none(self, position_group_repo, mock_session):
        """Test getting daily realized PnL when none."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_daily_realized_pnl(user_id)

        assert pnl == Decimal("0")


class TestGetTotalPnlForUser:
    """Test get_total_pnl_for_user method."""

    @pytest.mark.asyncio
    async def test_get_total_pnl_for_user(self, position_group_repo, mock_session):
        """Test getting total PnL for user."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("1500.00")
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_total_pnl_for_user(user_id)

        assert pnl == Decimal("1500.00")

    @pytest.mark.asyncio
    async def test_get_total_pnl_for_user_none(self, position_group_repo, mock_session):
        """Test getting total PnL when none."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_total_pnl_for_user(user_id)

        assert pnl == Decimal("0")


class TestGetTotalRealizedPnlOnly:
    """Test get_total_realized_pnl_only method."""

    @pytest.mark.asyncio
    async def test_get_total_realized_pnl_only(self, position_group_repo, mock_session):
        """Test getting total realized PnL only."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = Decimal("800.00")
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_total_realized_pnl_only(user_id)

        assert pnl == Decimal("800.00")

    @pytest.mark.asyncio
    async def test_get_total_realized_pnl_only_none(self, position_group_repo, mock_session):
        """Test getting total realized PnL when none."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        pnl = await position_group_repo.get_total_realized_pnl_only(user_id)

        assert pnl == Decimal("0")


class TestGetClosedByUser:
    """Test get_closed_by_user method."""

    @pytest.mark.asyncio
    async def test_get_closed_by_user(self, position_group_repo, mock_session):
        """Test getting closed position groups with pagination."""
        user_id = uuid.uuid4()
        mock_groups = [MagicMock(spec=PositionGroup) for _ in range(5)]

        # First call for count, second for data
        count_result = MagicMock()
        count_result.scalar.return_value = 10

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = mock_groups

        mock_session.execute.side_effect = [count_result, data_result]

        groups, total = await position_group_repo.get_closed_by_user(user_id, limit=5, offset=0)

        assert len(groups) == 5
        assert total == 10

    @pytest.mark.asyncio
    async def test_get_closed_by_user_clamps_limit(self, position_group_repo, mock_session):
        """Test that limit is clamped to max 500."""
        user_id = uuid.uuid4()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, data_result]

        await position_group_repo.get_closed_by_user(user_id, limit=1000, offset=0)

        # Should work without error, limit should be clamped internally

    @pytest.mark.asyncio
    async def test_get_closed_by_user_clamps_offset(self, position_group_repo, mock_session):
        """Test that negative offset is clamped to 0."""
        user_id = uuid.uuid4()

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [count_result, data_result]

        await position_group_repo.get_closed_by_user(user_id, limit=10, offset=-5)

        # Should work without error, offset should be clamped internally


class TestGetClosedByUserAll:
    """Test get_closed_by_user_all method."""

    @pytest.mark.asyncio
    async def test_get_closed_by_user_all(self, position_group_repo, mock_session):
        """Test getting all closed position groups."""
        user_id = uuid.uuid4()
        mock_groups = [MagicMock(spec=PositionGroup) for _ in range(10)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result

        groups = await position_group_repo.get_closed_by_user_all(user_id)

        assert len(groups) == 10


class TestIncrementPyramidCount:
    """Test increment_pyramid_count method."""

    @pytest.mark.asyncio
    async def test_increment_pyramid_count(self, position_group_repo, mock_session):
        """Test incrementing pyramid count."""
        group_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 2
        mock_session.execute.return_value = mock_result

        new_count = await position_group_repo.increment_pyramid_count(group_id)

        assert new_count == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_pyramid_count_with_dca_legs(self, position_group_repo, mock_session):
        """Test incrementing pyramid count with additional DCA legs."""
        group_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        mock_session.execute.return_value = mock_result

        new_count = await position_group_repo.increment_pyramid_count(group_id, additional_dca_legs=5)

        assert new_count == 3
        mock_session.execute.assert_called_once()
