"""
Tests for DCAOrderRepository - DCA Order database operations.
"""
import pytest
import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dca_order import DCAOrderRepository
from app.models.dca_order import DCAOrder, OrderStatus
from app.models.position_group import PositionGroup


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def dca_order_repo(mock_session):
    return DCAOrderRepository(mock_session)


class TestDCAOrderRepositoryInit:
    """Test DCAOrderRepository initialization."""

    def test_init(self, mock_session):
        repo = DCAOrderRepository(mock_session)
        assert repo.session == mock_session
        assert repo.model == DCAOrder


class TestGetOpenAndPartiallyFilledOrders:
    """Test get_open_and_partially_filled_orders methods."""

    @pytest.mark.asyncio
    async def test_get_open_and_partially_filled_orders_with_user_id(self, dca_order_repo, mock_session):
        """Test getting orders for a specific user."""
        user_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(spec=DCAOrder)]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders = await dca_order_repo.get_open_and_partially_filled_orders(user_id=user_id)

        assert len(orders) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_open_and_partially_filled_orders_without_user_id(self, dca_order_repo, mock_session):
        """Test getting all open orders without user filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(spec=DCAOrder), MagicMock(spec=DCAOrder)]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders = await dca_order_repo.get_open_and_partially_filled_orders(user_id=None)

        assert len(orders) == 2
        mock_session.execute.assert_called_once()


class TestGetAllOpenOrders:
    """Test get_all_open_orders method."""

    @pytest.mark.asyncio
    async def test_get_all_open_orders(self, dca_order_repo, mock_session):
        """Test getting all open orders."""
        mock_order1 = MagicMock(spec=DCAOrder)
        mock_order1.status = OrderStatus.OPEN.value
        mock_order2 = MagicMock(spec=DCAOrder)
        mock_order2.status = OrderStatus.OPEN.value

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_order1, mock_order2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders = await dca_order_repo.get_all_open_orders()

        assert len(orders) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_open_orders_empty(self, dca_order_repo, mock_session):
        """Test getting all open orders when none exist."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders = await dca_order_repo.get_all_open_orders()

        assert len(orders) == 0


class TestGetOpenOrdersByGroupId:
    """Test get_open_orders_by_group_id method."""

    @pytest.mark.asyncio
    async def test_get_open_orders_by_group_id(self, dca_order_repo, mock_session):
        """Test getting open orders for a specific position group."""
        group_id = str(uuid.uuid4())

        mock_order = MagicMock(spec=DCAOrder)
        mock_order.group_id = group_id
        mock_order.status = OrderStatus.OPEN.value

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_order]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders = await dca_order_repo.get_open_orders_by_group_id(group_id)

        assert len(orders) == 1
        mock_session.execute.assert_called_once()


class TestGetAllOrdersByGroupId:
    """Test get_all_orders_by_group_id method."""

    @pytest.mark.asyncio
    async def test_get_all_orders_by_group_id(self, dca_order_repo, mock_session):
        """Test getting all orders for a specific position group."""
        group_id = str(uuid.uuid4())

        mock_orders = [
            MagicMock(spec=DCAOrder, status=OrderStatus.OPEN.value),
            MagicMock(spec=DCAOrder, status=OrderStatus.FILLED.value),
            MagicMock(spec=DCAOrder, status=OrderStatus.CANCELLED.value),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_orders
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders = await dca_order_repo.get_all_orders_by_group_id(group_id)

        assert len(orders) == 3
        mock_session.execute.assert_called_once()


class TestGetAllOpenOrdersForAllUsers:
    """Test get_all_open_orders_for_all_users method."""

    @pytest.mark.asyncio
    async def test_get_all_open_orders_for_all_users_empty_list(self, dca_order_repo):
        """Test with empty user_ids list."""
        result = await dca_order_repo.get_all_open_orders_for_all_users([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_all_open_orders_for_all_users_with_orders(self, dca_order_repo, mock_session):
        """Test getting open orders for multiple users."""
        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())

        # Create mock orders with groups
        group1 = MagicMock()
        group1.user_id = user1_id
        order1 = MagicMock(spec=DCAOrder)
        order1.group = group1
        order1.status = OrderStatus.OPEN.value

        group2 = MagicMock()
        group2.user_id = user2_id
        order2 = MagicMock(spec=DCAOrder)
        order2.group = group2
        order2.status = OrderStatus.OPEN.value

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [order1, order2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders_by_user = await dca_order_repo.get_all_open_orders_for_all_users([user1_id, user2_id])

        assert user1_id in orders_by_user
        assert user2_id in orders_by_user
        assert len(orders_by_user[user1_id]) == 1
        assert len(orders_by_user[user2_id]) == 1

    @pytest.mark.asyncio
    async def test_get_all_open_orders_for_all_users_no_group(self, dca_order_repo, mock_session):
        """Test handling of orders without group."""
        user1_id = str(uuid.uuid4())

        # Create mock order without group
        order1 = MagicMock(spec=DCAOrder)
        order1.group = None

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [order1]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders_by_user = await dca_order_repo.get_all_open_orders_for_all_users([user1_id])

        # Order without group should not be included
        assert user1_id not in orders_by_user

    @pytest.mark.asyncio
    async def test_get_all_open_orders_for_all_users_multiple_orders_same_user(self, dca_order_repo, mock_session):
        """Test getting multiple orders for the same user."""
        user1_id = str(uuid.uuid4())

        group = MagicMock()
        group.user_id = user1_id

        order1 = MagicMock(spec=DCAOrder)
        order1.group = group
        order2 = MagicMock(spec=DCAOrder)
        order2.group = group

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [order1, order2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        orders_by_user = await dca_order_repo.get_all_open_orders_for_all_users([user1_id])

        assert user1_id in orders_by_user
        assert len(orders_by_user[user1_id]) == 2
