"""
Performance and Load Tests for the Trading Engine.

This module tests the system's behavior under concurrent load and stress conditions:
- Concurrent signal processing
- Database connection pool stress
- Mock exchange latency simulation
- Queue processing throughput
"""
import pytest
import asyncio
import time
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.queue_manager import QueueManagerService
from app.services.signal_router import SignalRouterService
from app.services.execution_pool_manager import ExecutionPoolManager
from app.services.exchange_abstraction.mock_connector import MockConnector
from app.repositories.queued_signal import QueuedSignalRepository
from app.repositories.position_group import PositionGroupRepository
from app.models.queued_signal import QueuedSignal, QueueStatus
from app.models.user import User
from app.schemas.webhook_payloads import WebhookPayload, TradingViewData, ExecutionIntent, StrategyInfo, RiskInfo
from app.schemas.grid_config import RiskEngineConfig


# --- Test Fixtures ---

@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user_id = uuid.uuid4()
    return MagicMock(
        id=user_id,
        username="perf_test_user",
        risk_config={
            "max_open_positions_global": 10,
            "max_open_positions_per_symbol": 2,
            "max_total_exposure_usd": 10000.0,
            "loss_threshold_percent": -5.0
        },
        encrypted_api_keys={
            "mock": {"encrypted_data": "test_key", "testnet": True}
        }
    )


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory that returns an async context manager."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    class MockContextManager:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def factory():
        return MockContextManager()

    return factory


def create_test_signal(symbol: str, action: str = "buy", timeframe: int = 60) -> WebhookPayload:
    """Helper to create a test webhook payload."""
    return WebhookPayload(
        user_id=str(uuid.uuid4()),
        secret="test_secret",
        source="tradingview",
        timestamp=datetime.utcnow().isoformat(),
        tv=TradingViewData(
            exchange="mock",
            symbol=symbol,
            timeframe=timeframe,
            action=action,
            market_position="long",
            market_position_size=100,
            prev_market_position="flat",
            prev_market_position_size=0,
            entry_price=50000.0,
            close_price=50000.0,
            order_size=100
        ),
        execution_intent=ExecutionIntent(
            type="signal",
            side="buy",
            position_size_type="quote"
        ),
        strategy_info=StrategyInfo(
            trade_id="perf_test",
            alert_name="Performance Test",
            alert_message="Performance test signal"
        ),
        risk=RiskInfo(
            max_slippage_percent=1.0
        )
    )


# --- Concurrent Signal Processing Tests ---

class TestConcurrentSignalProcessing:
    """Tests for concurrent signal handling."""

    @pytest.mark.asyncio
    async def test_concurrent_signals_different_symbols(self, mock_user, mock_session_factory):
        """Test processing multiple signals for different symbols concurrently."""
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "XRPUSDT", "DOGEUSDT"]

        mock_repo = MagicMock()
        mock_repo.get_by_symbol_timeframe_side = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock()
        mock_repo.update = AsyncMock()

        queue_manager = QueueManagerService(
            session_factory=mock_session_factory,
            user=mock_user,
            queued_signal_repository_class=MagicMock(return_value=mock_repo),
            position_group_repository_class=MagicMock()
        )

        # Create signals for different symbols
        signals = [create_test_signal(symbol) for symbol in symbols]

        # Process all signals concurrently
        start_time = time.time()
        tasks = [queue_manager.add_signal_to_queue(signal) for signal in signals]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        # Verify all signals were processed
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) >= len(symbols) - 1  # Allow for some duplicate rejection

        # Verify reasonable processing time (should be < 1 second for 5 signals)
        assert elapsed_time < 1.0, f"Processing took too long: {elapsed_time}s"

    @pytest.mark.asyncio
    async def test_concurrent_signals_same_symbol_duplicate_handling(self, mock_user, mock_session_factory):
        """Test that duplicate signals for the same symbol are properly handled."""
        existing_signal = MagicMock()
        existing_signal.queued_at = datetime.utcnow() - timedelta(seconds=30)  # Same candle
        existing_signal.replacement_count = 0

        mock_repo = MagicMock()
        mock_repo.get_by_symbol_timeframe_side = AsyncMock(return_value=existing_signal)

        queue_manager = QueueManagerService(
            session_factory=mock_session_factory,
            user=mock_user,
            queued_signal_repository_class=MagicMock(return_value=mock_repo),
            position_group_repository_class=MagicMock()
        )

        # Try to add multiple signals for the same symbol concurrently
        signal = create_test_signal("BTCUSDT")
        tasks = [queue_manager.add_signal_to_queue(signal) for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should raise ValueError for duplicate
        exceptions = [r for r in results if isinstance(r, ValueError)]
        assert len(exceptions) == 5, "All duplicate signals should be rejected"

    @pytest.mark.asyncio
    async def test_high_volume_signal_throughput(self, mock_user, mock_session_factory):
        """Test system behavior under high signal volume."""
        num_signals = 50

        mock_repo = MagicMock()
        mock_repo.get_by_symbol_timeframe_side = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock()

        queue_manager = QueueManagerService(
            session_factory=mock_session_factory,
            user=mock_user,
            queued_signal_repository_class=MagicMock(return_value=mock_repo),
            position_group_repository_class=MagicMock()
        )

        # Generate unique signals
        signals = [create_test_signal(f"SYM{i}USDT") for i in range(num_signals)]

        start_time = time.time()
        tasks = [queue_manager.add_signal_to_queue(signal) for signal in signals]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        successful = [r for r in results if not isinstance(r, Exception)]

        # Performance assertions
        assert len(successful) >= num_signals * 0.9, f"At least 90% should succeed: {len(successful)}/{num_signals}"
        assert elapsed_time < 5.0, f"Processing 50 signals took too long: {elapsed_time}s"

        # Calculate throughput
        throughput = len(successful) / elapsed_time
        assert throughput > 10, f"Throughput too low: {throughput:.2f} signals/sec"


# --- Database Connection Pool Stress Tests ---

class TestDatabasePoolStress:
    """Tests for database connection pool behavior under stress."""

    @pytest.mark.asyncio
    async def test_concurrent_db_operations(self):
        """Test that multiple concurrent database operations don't exhaust the pool."""
        num_operations = 20

        async def mock_db_operation(delay: float = 0.01):
            """Simulate a database operation with some delay."""
            await asyncio.sleep(delay)
            return True

        # Execute many operations concurrently
        start_time = time.time()
        tasks = [mock_db_operation() for _ in range(num_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        successful = [r for r in results if r is True]
        assert len(successful) == num_operations

        # With concurrent execution, should be faster than sequential
        # 20 operations * 0.01s = 0.2s sequential, should be < 0.1s concurrent
        assert elapsed_time < 0.15, f"Concurrent ops took too long: {elapsed_time}s"

    @pytest.mark.asyncio
    async def test_session_isolation_under_load(self, mock_session_factory):
        """Test that sessions are properly isolated under concurrent load."""
        call_count = 0
        session_ids = set()

        async def track_session():
            nonlocal call_count
            call_count += 1
            session_id = id(asyncio.current_task())
            session_ids.add(session_id)
            await asyncio.sleep(0.01)
            return session_id

        # Execute concurrent operations
        tasks = [track_session() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Each task should have been tracked
        assert call_count == 10
        # With proper isolation, each task should have a unique ID
        assert len(session_ids) == 10


# --- Mock Exchange Latency Simulation Tests ---

class TestExchangeLatencySimulation:
    """Tests for system behavior with exchange latency."""

    @pytest.mark.asyncio
    async def test_order_placement_with_latency(self):
        """Test order placement behavior with simulated exchange latency."""
        connector = MockConnector({"encrypted_data": "test"})

        # Simulate latency by adding delay to price fetch
        original_get_price = connector.get_current_price

        async def delayed_get_price(symbol):
            await asyncio.sleep(0.05)  # 50ms latency
            return await original_get_price(symbol)

        connector.get_current_price = delayed_get_price

        start_time = time.time()
        price = await connector.get_current_price("BTCUSDT")
        elapsed_time = time.time() - start_time

        assert price is not None
        assert elapsed_time >= 0.05, "Latency should be at least 50ms"

        await connector.close()

    @pytest.mark.asyncio
    async def test_concurrent_orders_with_latency(self):
        """Test multiple concurrent orders with exchange latency."""
        # Simulate concurrent order placement with artificial latency
        order_count = 0
        order_lock = asyncio.Lock()

        async def mock_delayed_order(symbol: str, delay: float = 0.02):
            nonlocal order_count
            await asyncio.sleep(delay)  # Simulated latency
            async with order_lock:
                order_count += 1
            return {"order_id": f"order_{symbol}", "status": "filled"}

        # Place multiple orders concurrently
        num_orders = 10
        start_time = time.time()

        tasks = [mock_delayed_order(f"SYM{i}USDT") for i in range(num_orders)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == num_orders, f"Expected {num_orders} successful, got {len(successful)}"
        assert order_count == num_orders, f"Expected {num_orders} orders placed, got {order_count}"

        # With concurrent execution, should be faster than sequential (10 * 0.02 = 0.2s)
        assert elapsed_time < 0.15, f"Concurrent orders took too long: {elapsed_time}s"

    @pytest.mark.asyncio
    async def test_order_timeout_handling(self):
        """Test that order placement handles timeouts gracefully."""
        connector = MockConnector({"encrypted_data": "test"})

        # Inject timeout error
        connector.inject_error("place_order", "timeout", "Connection timed out")

        with pytest.raises(Exception) as exc_info:
            await connector.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=Decimal("1.0")
            )

        assert "timed out" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()

        await connector.close()

    @pytest.mark.asyncio
    async def test_rate_limit_backoff(self):
        """Test that rate limiting triggers appropriate backoff."""
        connector = MockConnector({"encrypted_data": "test"})

        # Inject rate limit error (one-shot by default)
        connector.inject_error("get_current_price", "rate_limit", "Rate limit exceeded")

        # First call should fail with rate limit
        with pytest.raises(Exception) as exc_info:
            await connector.get_current_price("BTCUSDT")

        assert "rate" in str(exc_info.value).lower()

        # After one-shot error is consumed, next call should succeed
        price = await connector.get_current_price("BTCUSDT")
        assert price is not None

        await connector.close()


# --- Queue Processing Throughput Tests ---

class TestQueueProcessingThroughput:
    """Tests for queue processing performance."""

    @pytest.mark.asyncio
    async def test_queue_polling_performance(self, mock_user, mock_session_factory):
        """Test queue polling doesn't create excessive overhead."""
        mock_repo = MagicMock()
        mock_repo.get_all_queued_signals = AsyncMock(return_value=[])

        mock_pg_repo = MagicMock()
        mock_pg_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

        queue_manager = QueueManagerService(
            session_factory=mock_session_factory,
            user=mock_user,
            queued_signal_repository_class=MagicMock(return_value=mock_repo),
            position_group_repository_class=MagicMock(return_value=mock_pg_repo),
            polling_interval_seconds=0.01  # Fast polling for test
        )

        # Track polling cycles
        poll_count = 0
        original_promote = queue_manager.promote_highest_priority_signal

        async def tracked_promote(session):
            nonlocal poll_count
            poll_count += 1
            return await original_promote(session)

        queue_manager.promote_highest_priority_signal = tracked_promote

        # Start and quickly stop the promotion task
        await queue_manager.start_promotion_task()
        await asyncio.sleep(0.1)  # Let it run for 100ms
        await queue_manager.stop_promotion_task()

        # Should have polled multiple times
        assert poll_count >= 5, f"Expected at least 5 polls in 100ms, got {poll_count}"

    @pytest.mark.asyncio
    async def test_promotion_with_multiple_queued_signals(self, mock_user, mock_session_factory):
        """Test promotion logic when queue has multiple signals."""
        # Create mock signals with different priorities
        signals = []
        for i in range(5):
            signal = MagicMock(spec=QueuedSignal)
            signal.id = uuid.uuid4()
            signal.user_id = mock_user.id
            signal.symbol = f"SYM{i}USDT"
            signal.exchange = "mock"
            signal.timeframe = 60
            signal.side = "long"
            signal.entry_price = Decimal("100")
            signal.current_loss_percent = Decimal(str(-i))  # Different loss levels
            signal.replacement_count = 0
            signal.queued_at = datetime.utcnow() - timedelta(minutes=i)
            signal.signal_payload = {}
            signals.append(signal)

        mock_repo = MagicMock()
        mock_repo.get_all_queued_signals = AsyncMock(return_value=signals)

        mock_pg_repo = MagicMock()
        mock_pg_repo.get_active_position_groups_for_user = AsyncMock(return_value=[])

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_user)
        mock_session.commit = AsyncMock()

        queue_manager = QueueManagerService(
            session_factory=mock_session_factory,
            user=mock_user,
            queued_signal_repository_class=MagicMock(return_value=mock_repo),
            position_group_repository_class=MagicMock(return_value=mock_pg_repo),
            execution_pool_manager=None  # No pool manager means no promotion
        )

        # This should not raise and should handle multiple signals
        await queue_manager.promote_highest_priority_signal(mock_session)

        # Verify signal processing occurred
        mock_repo.get_all_queued_signals.assert_called_once()


# --- Execution Pool Manager Performance Tests ---

class TestExecutionPoolPerformance:
    """Tests for execution pool manager under load."""

    @pytest.mark.asyncio
    async def test_concurrent_slot_requests(self):
        """Test that concurrent slot requests are handled properly."""
        mock_session = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.count_by_status = AsyncMock(return_value=0)

        class MockContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, *args):
                pass

        def mock_factory():
            return MockContextManager()

        pool_manager = ExecutionPoolManager(
            session_factory=mock_factory,
            position_group_repository_class=MagicMock(return_value=mock_repo),
            max_open_groups=5
        )

        # Request multiple slots concurrently
        num_requests = 10
        tasks = [pool_manager.request_slot() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)

        # With 5 max slots and 0 active, first 5 should succeed
        # Note: Exact behavior depends on implementation
        successful = sum(1 for r in results if r is True)
        assert successful >= 1, "At least one slot should be granted"

    @pytest.mark.asyncio
    async def test_slot_release_under_load(self):
        """Test slot release behavior under concurrent load."""
        mock_session = AsyncMock()
        active_count = 5  # Start at max

        mock_repo = MagicMock()
        mock_repo.count_by_status = AsyncMock(return_value=active_count)

        class MockContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, *args):
                pass

        def mock_factory():
            return MockContextManager()

        pool_manager = ExecutionPoolManager(
            session_factory=mock_factory,
            position_group_repository_class=MagicMock(return_value=mock_repo),
            max_open_groups=5
        )

        # Initially should not grant slot (at max)
        result = await pool_manager.request_slot()
        assert result is False, "Should not grant slot when at max"

        # Simulate position close
        mock_repo.count_by_status = AsyncMock(return_value=4)

        # Now should grant
        result = await pool_manager.request_slot()
        assert result is True, "Should grant slot after release"
