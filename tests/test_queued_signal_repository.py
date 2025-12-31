"""
Tests for QueuedSignalRepository - Queued signal database operations.
"""
import pytest
import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.queued_signal import QueuedSignalRepository
from app.models.queued_signal import QueuedSignal, QueueStatus


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def queued_signal_repo(mock_session):
    return QueuedSignalRepository(mock_session)


class TestQueuedSignalRepositoryInit:
    """Test QueuedSignalRepository initialization."""

    def test_init(self, mock_session):
        repo = QueuedSignalRepository(mock_session)
        assert repo.session == mock_session
        assert repo.model == QueuedSignal


class TestGetById:
    """Test get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, queued_signal_repo, mock_session):
        """Test getting a signal by ID."""
        signal_id = str(uuid.uuid4())
        mock_signal = MagicMock(spec=QueuedSignal)
        mock_signal.id = signal_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_signal
        mock_session.execute.return_value = mock_result

        # Patch the get method from base class
        with patch.object(queued_signal_repo, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_signal
            signal = await queued_signal_repo.get_by_id(signal_id)
            assert signal == mock_signal
            mock_get.assert_called_once_with(signal_id)

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, queued_signal_repo, mock_session):
        """Test getting a signal by ID when not found."""
        with patch.object(queued_signal_repo, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            signal = await queued_signal_repo.get_by_id(str(uuid.uuid4()))
            assert signal is None


class TestGetAllQueuedSignals:
    """Test get_all_queued_signals method."""

    @pytest.mark.asyncio
    async def test_get_all_queued_signals(self, queued_signal_repo, mock_session):
        """Test getting all queued signals."""
        mock_signals = [MagicMock(spec=QueuedSignal) for _ in range(3)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_all_queued_signals()

        assert len(signals) == 3

    @pytest.mark.asyncio
    async def test_get_all_queued_signals_with_for_update(self, queued_signal_repo, mock_session):
        """Test getting all queued signals with FOR UPDATE lock."""
        mock_signals = [MagicMock(spec=QueuedSignal)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_all_queued_signals(for_update=True)

        assert len(signals) == 1
        mock_session.execute.assert_called_once()


class TestGetAllQueuedSignalsForUser:
    """Test get_all_queued_signals_for_user method."""

    @pytest.mark.asyncio
    async def test_get_all_queued_signals_for_user(self, queued_signal_repo, mock_session):
        """Test getting queued signals for a specific user."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal) for _ in range(2)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_all_queued_signals_for_user(user_id)

        assert len(signals) == 2

    @pytest.mark.asyncio
    async def test_get_all_queued_signals_for_user_with_for_update(self, queued_signal_repo, mock_session):
        """Test getting queued signals for user with FOR UPDATE lock."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_all_queued_signals_for_user(user_id, for_update=True)

        assert len(signals) == 1


class TestGetHistoryForUser:
    """Test get_history_for_user method."""

    @pytest.mark.asyncio
    async def test_get_history_for_user(self, queued_signal_repo, mock_session):
        """Test getting signal history for a specific user."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal) for _ in range(5)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        history = await queued_signal_repo.get_history_for_user(user_id, limit=10)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_get_history_for_user_default_limit(self, queued_signal_repo, mock_session):
        """Test getting signal history with default limit."""
        user_id = str(uuid.uuid4())
        mock_signals = []

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        history = await queued_signal_repo.get_history_for_user(user_id)  # Default limit=50

        assert len(history) == 0


class TestGetHistory:
    """Test get_history method."""

    @pytest.mark.asyncio
    async def test_get_history(self, queued_signal_repo, mock_session):
        """Test getting all signal history."""
        mock_signals = [MagicMock(spec=QueuedSignal) for _ in range(10)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        history = await queued_signal_repo.get_history(limit=20)

        assert len(history) == 10


class TestGetQueuedSignalsForSymbol:
    """Test get_queued_signals_for_symbol method."""

    @pytest.mark.asyncio
    async def test_get_queued_signals_for_symbol_basic(self, queued_signal_repo, mock_session):
        """Test getting queued signals for a symbol."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance"
        )

        assert len(signals) == 1

    @pytest.mark.asyncio
    async def test_get_queued_signals_for_symbol_with_timeframe(self, queued_signal_repo, mock_session):
        """Test getting queued signals for a symbol with timeframe filter."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=60
        )

        assert len(signals) == 1

    @pytest.mark.asyncio
    async def test_get_queued_signals_for_symbol_with_side(self, queued_signal_repo, mock_session):
        """Test getting queued signals for a symbol with side filter."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            side="buy"
        )

        assert len(signals) == 1

    @pytest.mark.asyncio
    async def test_get_queued_signals_for_symbol_all_filters(self, queued_signal_repo, mock_session):
        """Test getting queued signals for a symbol with all filters."""
        user_id = str(uuid.uuid4())
        mock_signals = [MagicMock(spec=QueuedSignal)]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        signals = await queued_signal_repo.get_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=60,
            side="buy"
        )

        assert len(signals) == 1


class TestCancelQueuedSignalsForSymbol:
    """Test cancel_queued_signals_for_symbol method."""

    @pytest.mark.asyncio
    async def test_cancel_queued_signals_for_symbol(self, queued_signal_repo, mock_session):
        """Test cancelling queued signals for a symbol."""
        user_id = str(uuid.uuid4())
        signal1 = MagicMock(spec=QueuedSignal)
        signal1.id = uuid.uuid4()
        signal2 = MagicMock(spec=QueuedSignal)
        signal2.id = uuid.uuid4()
        mock_signals = [signal1, signal2]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Mock delete to succeed
        queued_signal_repo.delete = AsyncMock()

        count = await queued_signal_repo.cancel_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance"
        )

        assert count == 2
        assert queued_signal_repo.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_cancel_queued_signals_for_symbol_none_found(self, queued_signal_repo, mock_session):
        """Test cancelling when no signals found."""
        user_id = str(uuid.uuid4())

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        count = await queued_signal_repo.cancel_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance"
        )

        assert count == 0

    @pytest.mark.asyncio
    async def test_cancel_queued_signals_for_symbol_with_filters(self, queued_signal_repo, mock_session):
        """Test cancelling queued signals with timeframe and side filters."""
        user_id = str(uuid.uuid4())
        signal1 = MagicMock(spec=QueuedSignal)
        signal1.id = uuid.uuid4()
        mock_signals = [signal1]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_signals
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        queued_signal_repo.delete = AsyncMock()

        count = await queued_signal_repo.cancel_queued_signals_for_symbol(
            user_id=user_id,
            symbol="BTCUSDT",
            exchange="binance",
            timeframe=60,
            side="buy"
        )

        assert count == 1
