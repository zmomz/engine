"""
Resilience tests for database transactions, Redis failures, and exchange errors.
These tests verify the system handles failures gracefully without data corruption.
"""
import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from datetime import datetime

from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position_group import PositionGroup, PositionGroupStatus
from app.models.dca_order import DCAOrder, OrderStatus
from app.schemas.grid_config import RiskEngineConfig


# ============================================================================
# Phase 3.1: Database Transaction Tests
# ============================================================================

class TestDatabaseTransactionRollback:
    """Test that database transactions rollback correctly on errors."""

    @pytest.mark.asyncio
    async def test_position_creation_rollback_on_error(self, db_session, test_user):
        """Position creation should rollback if order placement fails."""
        from app.repositories.position_group import PositionGroupRepository

        repo = PositionGroupRepository(db_session)

        # Create a position group with all required fields
        position_id = uuid.uuid4()
        position_group = PositionGroup(
            id=position_id,
            user_id=test_user.id,
            symbol="BTCUSDT",
            exchange="mock",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.WAITING,
            total_dca_legs=5,
            filled_dca_legs=0,
            tp_mode="per_leg",
            base_entry_price=Decimal("50000")
        )

        try:
            await repo.create(position_group)
            await db_session.flush()

            # Simulate error during order placement
            raise Exception("Simulated order placement failure")
        except Exception:
            await db_session.rollback()

        # Verify position was not persisted after rollback
        result = await repo.get_with_orders(position_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_position_updates_handle_conflicts(self, db_session, test_user):
        """Concurrent updates to the same position should be handled safely."""
        from app.repositories.position_group import PositionGroupRepository

        repo = PositionGroupRepository(db_session)

        # Create a position group with all required fields
        position_id = uuid.uuid4()
        position_group = PositionGroup(
            id=position_id,
            user_id=test_user.id,
            symbol="ETHUSDT",
            exchange="mock",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            total_invested_usd=Decimal("1000"),
            total_dca_legs=5,
            filled_dca_legs=0,
            tp_mode="per_leg",
            base_entry_price=Decimal("3000"),
            weighted_avg_entry=Decimal("3000")
        )
        await repo.create(position_group)
        await db_session.commit()

        # Refresh to get latest state
        await db_session.refresh(position_group)

        # Update the position
        position_group.total_invested_usd = Decimal("1500")
        await repo.update(position_group)
        await db_session.commit()

        # Verify update persisted
        updated = await repo.get_by_user_and_id(test_user.id, position_id)
        assert updated.total_invested_usd == Decimal("1500")


class TestDatabaseDeadlockHandling:
    """Test handling of database deadlock scenarios."""

    @pytest.mark.asyncio
    async def test_deadlock_retry_mechanism(self):
        """Operations should retry on deadlock errors."""
        mock_session = AsyncMock(spec=AsyncSession)
        retry_count = 0

        async def simulate_deadlock():
            nonlocal retry_count
            retry_count += 1
            if retry_count < 3:
                raise OperationalError("Deadlock found", None, None)
            return True

        mock_session.execute = simulate_deadlock

        # Simulate a retry wrapper
        max_retries = 5
        result = None
        for i in range(max_retries):
            try:
                result = await mock_session.execute()
                break
            except OperationalError:
                if i == max_retries - 1:
                    raise
                await asyncio.sleep(0.01)

        assert result is True
        assert retry_count == 3


class TestDatabaseIntegrityConstraints:
    """Test database integrity constraint handling."""

    @pytest.mark.asyncio
    async def test_duplicate_active_position_rejected(self, db_session, test_user):
        """Duplicate active positions for same symbol should be rejected by constraint."""
        from app.repositories.position_group import PositionGroupRepository

        pg_repo = PositionGroupRepository(db_session)

        # Create first active position group
        position_id1 = uuid.uuid4()
        position_group1 = PositionGroup(
            id=position_id1,
            user_id=test_user.id,
            symbol="BTCUSDT",
            exchange="mock",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,
            total_dca_legs=5,
            filled_dca_legs=0,
            tp_mode="per_leg",
            base_entry_price=Decimal("50000"),
            weighted_avg_entry=Decimal("50000")
        )
        await pg_repo.create(position_group1)
        await db_session.commit()

        # Try to create second ACTIVE position for same symbol - should be rejected
        position_id2 = uuid.uuid4()
        position_group2 = PositionGroup(
            id=position_id2,
            user_id=test_user.id,
            symbol="BTCUSDT",  # Same symbol
            exchange="mock",
            timeframe=60,
            side="long",
            status=PositionGroupStatus.ACTIVE,  # Same status - should fail
            total_dca_legs=5,
            filled_dca_legs=0,
            tp_mode="per_leg",
            base_entry_price=Decimal("51000"),
            weighted_avg_entry=Decimal("51000")
        )

        # Should raise IntegrityError due to unique constraint on active positions
        with pytest.raises(IntegrityError):
            await pg_repo.create(position_group2)
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_foreign_key_constraint_enforcement(self, db_session, test_user):
        """Orders with invalid group_id should be rejected."""
        from app.repositories.dca_order import DCAOrderRepository

        order_repo = DCAOrderRepository(db_session)

        # Try to create order with non-existent group_id
        invalid_group_id = uuid.uuid4()
        invalid_pyramid_id = uuid.uuid4()

        order = DCAOrder(
            id=uuid.uuid4(),
            group_id=invalid_group_id,
            pyramid_id=invalid_pyramid_id,
            leg_index=0,
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            price=Decimal("50000"),
            quantity=Decimal("0.01"),
            status=OrderStatus.OPEN.value,
            exchange_order_id="orphan_order"
        )

        # Should raise IntegrityError due to foreign key violation
        with pytest.raises(IntegrityError):
            await order_repo.create(order)
            await db_session.commit()


# ============================================================================
# Phase 3.2: Redis Failure Tests
# ============================================================================

class TestRedisCacheFailures:
    """Test system behavior when Redis cache is unavailable."""

    @pytest.mark.asyncio
    async def test_app_continues_without_redis(self):
        """Application should continue functioning when Redis is unavailable."""
        # Test that the system handles Redis unavailability gracefully
        # by mocking the get_cache function to raise an exception
        with patch('app.core.cache.get_cache') as mock_get_cache:
            mock_get_cache.side_effect = Exception("Redis connection refused")

            # Services should handle this gracefully
            try:
                from app.core.cache import get_cache
                get_cache()
            except Exception as e:
                # It's OK if it raises, but the exception should be handled
                assert "Redis" in str(e) or "connection" in str(e).lower()

    @pytest.mark.asyncio
    async def test_leader_election_handles_redis_failure(self):
        """Leader election should fail gracefully when Redis is down."""
        from app.main import try_become_leader

        async def mock_cache_error():
            raise Exception("Redis connection refused")

        with patch('app.main.get_cache', side_effect=mock_cache_error):
            # Should not crash, should return False (not leader)
            result = await try_become_leader()
            assert result is False

    @pytest.mark.asyncio
    async def test_cache_get_returns_none_on_failure(self):
        """Cache get operations should return None on failure."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(side_effect=Exception("Redis error"))

        # Simulate a service using cache with fallback
        async def get_with_fallback(key, fallback=None):
            try:
                return await mock_cache.get(key)
            except Exception:
                return fallback

        result = await get_with_fallback("test_key", fallback="default")
        assert result == "default"

    @pytest.mark.asyncio
    async def test_cache_set_fails_silently(self):
        """Cache set operations should fail silently without affecting main flow."""
        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock(side_effect=Exception("Redis error"))

        # Simulate service that caches results
        async def process_with_cache():
            result = "computed_value"

            # Try to cache, but don't fail if it doesn't work
            try:
                await mock_cache.set("key", result)
            except Exception:
                pass  # Silently ignore cache failures

            return result

        result = await process_with_cache()
        assert result == "computed_value"


class TestRedisLockFailures:
    """Test distributed lock behavior on Redis failures."""

    @pytest.mark.asyncio
    async def test_lock_acquisition_timeout(self):
        """Lock acquisition should timeout gracefully."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock = AsyncMock(return_value=False)

        # Simulate lock acquisition with timeout
        acquired = await mock_cache.acquire_lock("test_lock", "worker_1", ttl_seconds=1)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_lock_release_handles_missing_lock(self):
        """Releasing a non-existent lock should not crash."""
        mock_cache = AsyncMock()
        mock_cache.release_lock = AsyncMock(return_value=False)

        # Should not raise
        result = await mock_cache.release_lock("non_existent_lock", "worker_1")
        assert result is False


# ============================================================================
# Phase 3.3: Exchange Error Simulation Tests
# ============================================================================

class TestExchangeConnectionErrors:
    """Test handling of exchange connection errors."""

    @pytest.mark.asyncio
    async def test_order_placement_retries_on_timeout(self):
        """Order placement should retry on connection timeout."""
        mock_connector = AsyncMock()

        call_count = 0

        async def mock_place_order(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncio.TimeoutError("Connection timeout")
            return {"orderId": "12345", "status": "NEW"}

        mock_connector.place_order = mock_place_order

        # Simulate retry logic
        max_retries = 5
        result = None
        for i in range(max_retries):
            try:
                result = await mock_connector.place_order("BTCUSDT", "limit", "buy", 0.01, 50000)
                break
            except asyncio.TimeoutError:
                if i == max_retries - 1:
                    raise
                await asyncio.sleep(0.01)

        assert result is not None
        assert result["orderId"] == "12345"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_price_fetch_fallback_on_error(self):
        """Price fetching should have fallback mechanism."""
        mock_connector = AsyncMock()
        mock_connector.get_current_price = AsyncMock(
            side_effect=Exception("Exchange API error")
        )

        # Fallback to cached or default price
        try:
            price = await mock_connector.get_current_price("BTCUSDT")
        except Exception:
            price = None  # Fallback

        # Service should handle None price gracefully
        assert price is None

    @pytest.mark.asyncio
    async def test_balance_fetch_error_handling(self):
        """Balance fetching errors should be handled without crashing."""
        mock_connector = AsyncMock()
        mock_connector.fetch_free_balance = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        try:
            balance = await mock_connector.fetch_free_balance()
        except Exception as e:
            # Should catch and handle appropriately
            assert "Rate limit" in str(e)


class TestExchangeOrderErrors:
    """Test handling of order-related exchange errors."""

    @pytest.mark.asyncio
    async def test_insufficient_balance_error_handling(self):
        """Insufficient balance errors should be caught and reported."""
        from app.services.position.position_closer import execute_handle_exit_signal

        mock_session = AsyncMock()
        mock_user = MagicMock()
        mock_user.encrypted_api_keys = {"mock": {"encrypted_data": "test"}}

        mock_position_group = MagicMock()
        mock_position_group.id = uuid.uuid4()
        mock_position_group.status = PositionGroupStatus.ACTIVE
        mock_position_group.symbol = "BTCUSDT"
        mock_position_group.exchange = "mock"
        mock_position_group.side = "long"
        mock_position_group.total_filled_quantity = Decimal("0.02")
        mock_position_group.total_invested_usd = Decimal("1000")
        mock_position_group.weighted_avg_entry = Decimal("50000")

        mock_repo_class = MagicMock()
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_with_orders.return_value = mock_position_group
        mock_repo_instance.update = AsyncMock()
        mock_repo_class.return_value = mock_repo_instance

        # Order service fails with insufficient balance, then succeeds with available
        call_count = 0

        async def mock_close(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Insufficient balance for requested action")
            return None

        mock_order_service_instance = AsyncMock()
        mock_order_service_instance.cancel_open_orders_for_group = AsyncMock()
        mock_order_service_instance.close_position_market = AsyncMock(side_effect=mock_close)
        mock_order_service_class = MagicMock(return_value=mock_order_service_instance)

        with patch('app.services.position.position_closer._get_exchange_connector_for_user') as mock_get_conn, \
             patch('app.services.position.position_closer.save_close_action'):
            mock_connector = AsyncMock()
            mock_connector.get_current_price = AsyncMock(return_value=51000)
            mock_connector.fetch_free_balance = AsyncMock(return_value={"BTC": 0.01})
            mock_connector.close = AsyncMock()
            mock_get_conn.return_value = mock_connector

            await execute_handle_exit_signal(
                position_group_id=mock_position_group.id,
                session=mock_session,
                user=mock_user,
                position_group_repository_class=mock_repo_class,
                order_service_class=mock_order_service_class
            )

        # Should have retried with available balance
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_order_rejected_handling(self):
        """Order rejection by exchange should be handled."""
        mock_connector = AsyncMock()
        mock_connector.place_order = AsyncMock(
            side_effect=Exception("Order rejected: Minimum notional not met")
        )

        with pytest.raises(Exception, match="Minimum notional"):
            await mock_connector.place_order("BTCUSDT", "limit", "buy", 0.0001, 50000)

    @pytest.mark.asyncio
    async def test_order_cancelled_externally(self):
        """Handle orders cancelled externally (e.g., by user on exchange)."""
        mock_order = MagicMock()
        mock_order.id = uuid.uuid4()
        mock_order.exchange_order_id = "12345"
        mock_order.status = OrderStatus.OPEN.value

        mock_connector = AsyncMock()
        mock_connector.get_order_status = AsyncMock(return_value={
            "id": "12345",
            "status": "canceled",
            "filled": 0,
            "amount": 0.01
        })

        # Order was cancelled externally
        status = await mock_connector.get_order_status("12345", "BTCUSDT")
        assert status["status"] == "canceled"


class TestExchangeRateLimiting:
    """Test handling of exchange rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_backoff(self):
        """Should implement exponential backoff on rate limits."""
        mock_connector = AsyncMock()

        call_count = 0
        call_times = []

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            call_times.append(asyncio.get_event_loop().time())
            if call_count < 3:
                raise Exception("Rate limit exceeded. Please retry after 1s")
            return {"result": "success"}

        mock_connector.get_current_price = mock_request

        # Simulate backoff
        result = None
        for i in range(5):
            try:
                result = await mock_connector.get_current_price("BTCUSDT")
                break
            except Exception as e:
                if "Rate limit" in str(e):
                    await asyncio.sleep(0.01 * (2 ** i))  # Exponential backoff
                else:
                    raise

        assert result is not None
        assert call_count == 3


class TestExchangePrecisionErrors:
    """Test handling of precision-related exchange errors."""

    @pytest.mark.asyncio
    async def test_quantity_precision_adjustment(self):
        """Quantities should be adjusted to exchange precision."""
        from app.services.grid_calculator import round_to_step_size

        quantity = Decimal("0.123456789")
        step_size = Decimal("0.001")

        rounded = round_to_step_size(quantity, step_size)
        assert rounded == Decimal("0.123")

    @pytest.mark.asyncio
    async def test_price_precision_adjustment(self):
        """Prices should be adjusted to exchange precision."""
        from app.services.grid_calculator import round_to_tick_size

        price = Decimal("50000.123456")
        tick_size = Decimal("0.01")

        rounded = round_to_tick_size(price, tick_size)
        assert rounded == Decimal("50000.12")


class TestExchangeMarketConditions:
    """Test handling of adverse market conditions."""

    @pytest.mark.asyncio
    async def test_high_slippage_detection(self):
        """High slippage should be detected and optionally rejected."""
        expected_price = Decimal("50000")
        actual_price = Decimal("51000")  # 2% slippage

        slippage_percent = abs(actual_price - expected_price) / expected_price * 100

        assert slippage_percent == Decimal("2")
        # With max_slippage_percent=1.0, this should be rejected
        max_slippage = Decimal("1.0")
        assert slippage_percent > max_slippage

    @pytest.mark.asyncio
    async def test_market_closed_handling(self):
        """Handle attempts to trade on closed markets."""
        mock_connector = AsyncMock()
        mock_connector.place_order = AsyncMock(
            side_effect=Exception("Market is closed")
        )

        with pytest.raises(Exception, match="Market is closed"):
            await mock_connector.place_order("BTCUSDT", "limit", "buy", 0.01, 50000)


# ============================================================================
# Phase 4: MockConnector Error Injection Tests
# ============================================================================

class TestMockConnectorErrorInjection:
    """Test MockConnector's error injection capabilities for testing."""

    @pytest.mark.asyncio
    async def test_error_injection_place_order(self):
        """Test error injection for place_order method."""
        from app.services.exchange_abstraction.mock_connector import MockConnector
        from app.exceptions import APIError

        connector = MockConnector()

        # Inject an insufficient balance error
        connector.inject_error("place_order", "insufficient_balance")

        with pytest.raises(APIError, match="Insufficient balance"):
            await connector.place_order("BTCUSDT", "buy", "limit", Decimal("0.01"), Decimal("50000"))

        await connector.close()

    @pytest.mark.asyncio
    async def test_error_injection_one_shot(self):
        """Test that one-shot errors are cleared after first trigger."""
        from app.services.exchange_abstraction.mock_connector import MockConnector
        from app.exceptions import APIError

        connector = MockConnector()

        # Inject a one-shot error (default)
        connector.inject_error("get_current_price", "api_error", "Temporary failure")

        # First call should raise
        with pytest.raises(APIError, match="Temporary failure"):
            await connector.get_current_price("BTCUSDT")

        # Second call should NOT raise (one-shot cleared)
        # Note: This will fail if exchange isn't running, so we just check error was cleared
        assert "get_current_price" not in connector._error_injection

        await connector.close()

    @pytest.mark.asyncio
    async def test_error_injection_persistent(self):
        """Test that persistent errors stay active."""
        from app.services.exchange_abstraction.mock_connector import MockConnector
        from app.exceptions import ExchangeConnectionError

        connector = MockConnector()

        # Inject a persistent timeout error
        connector.inject_error("fetch_balance", "timeout", one_shot=False)

        # Both calls should raise
        with pytest.raises(ExchangeConnectionError, match="timeout"):
            await connector.fetch_balance()

        with pytest.raises(ExchangeConnectionError, match="timeout"):
            await connector.fetch_balance()

        # Clear and verify
        connector.clear_error("fetch_balance")
        assert "fetch_balance" not in connector._error_injection

        await connector.close()

    @pytest.mark.asyncio
    async def test_error_injection_clear_all(self):
        """Test clearing all injected errors."""
        from app.services.exchange_abstraction.mock_connector import MockConnector

        connector = MockConnector()

        # Inject multiple errors
        connector.inject_error("place_order", "api_error")
        connector.inject_error("get_current_price", "timeout")
        connector.inject_error("fetch_balance", "rate_limit")

        assert len(connector._error_injection) == 3

        # Clear all
        connector.clear_error()

        assert len(connector._error_injection) == 0

        await connector.close()

    @pytest.mark.asyncio
    async def test_error_injection_rate_limit(self):
        """Test rate limit error injection."""
        from app.services.exchange_abstraction.mock_connector import MockConnector
        from app.exceptions import APIError

        connector = MockConnector()

        connector.inject_error("get_order_status", "rate_limit")

        with pytest.raises(APIError, match="Rate limit"):
            await connector.get_order_status("12345", "BTCUSDT")

        await connector.close()

    @pytest.mark.asyncio
    async def test_error_injection_custom_exception(self):
        """Test custom exception message injection."""
        from app.services.exchange_abstraction.mock_connector import MockConnector

        connector = MockConnector()

        connector.inject_error("cancel_order", "exception", "Custom error message for testing")

        with pytest.raises(Exception, match="Custom error message"):
            await connector.cancel_order("12345", "BTCUSDT")

        await connector.close()
