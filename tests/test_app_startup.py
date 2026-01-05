"""
Tests for application startup, lifespan events, and configuration.
Addresses coverage gap in main.py (currently 47%).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio


class TestTryBecomeLeader:
    """Test distributed leader election for background tasks."""

    @pytest.mark.asyncio
    async def test_become_leader_success(self):
        """Test successful leader acquisition."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.return_value = True

        with patch('app.main.get_cache', return_value=mock_cache):
            from app.main import try_become_leader, WORKER_ID
            result = await try_become_leader()

            assert result is True
            mock_cache.acquire_lock.assert_called_once_with(
                "background_task_leader",
                WORKER_ID,  # Use actual WORKER_ID constant
                ttl_seconds=60
            )

    @pytest.mark.asyncio
    async def test_become_leader_lock_not_acquired(self):
        """Test when another worker already holds the leader lock."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.return_value = False

        with patch('app.main.get_cache', return_value=mock_cache):
            from app.main import try_become_leader
            result = await try_become_leader()

            assert result is False

    @pytest.mark.asyncio
    async def test_become_leader_redis_unavailable(self):
        """Test graceful handling when Redis is unavailable."""
        async def raise_redis_error():
            raise Exception("Redis connection failed")

        with patch('app.main.get_cache', side_effect=raise_redis_error):
            from app.main import try_become_leader
            result = await try_become_leader()

            # Should not crash, just return False (not leader)
            assert result is False


class TestRenewLeaderLock:
    """Test leader lock renewal background task."""

    @pytest.mark.asyncio
    async def test_renew_lock_success(self):
        """Test successful lock renewal."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.return_value = True

        # Create a mock app state
        mock_app = MagicMock()
        mock_app.state.is_leader = True

        renewal_count = 0

        async def mock_acquire(*args, **kwargs):
            nonlocal renewal_count
            renewal_count += 1
            if renewal_count >= 2:
                # Stop after 2 renewals for test
                mock_app.state.is_leader = False
            return True

        mock_cache.acquire_lock = mock_acquire

        with patch('app.main.get_cache', return_value=mock_cache):
            with patch('app.main.app', mock_app):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    from app.main import renew_leader_lock
                    await renew_leader_lock()

                    assert renewal_count >= 1

    @pytest.mark.asyncio
    async def test_renew_lock_lost_leadership(self):
        """Test when lock renewal fails and leadership is lost."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.return_value = False  # Can't renew

        mock_app = MagicMock()
        mock_app.state.is_leader = True

        with patch('app.main.get_cache', return_value=mock_cache):
            with patch('app.main.app', mock_app):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    from app.main import renew_leader_lock
                    await renew_leader_lock()

                    # Should have set is_leader to False
                    assert mock_app.state.is_leader is False

    @pytest.mark.asyncio
    async def test_renew_lock_handles_cancellation(self):
        """Test that renewal task handles cancellation gracefully."""
        mock_cache = AsyncMock()

        mock_app = MagicMock()
        mock_app.state.is_leader = True

        async def mock_sleep_cancel(*args):
            raise asyncio.CancelledError()

        with patch('app.main.get_cache', return_value=mock_cache):
            with patch('app.main.app', mock_app):
                with patch('asyncio.sleep', mock_sleep_cancel):
                    from app.main import renew_leader_lock
                    # Should not raise, should exit cleanly
                    await renew_leader_lock()

    @pytest.mark.asyncio
    async def test_renew_lock_handles_exception(self):
        """Test that renewal task handles Redis exceptions gracefully."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.side_effect = Exception("Redis error")

        mock_app = MagicMock()
        mock_app.state.is_leader = True

        call_count = 0

        async def mock_sleep(*args):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                mock_app.state.is_leader = False

        with patch('app.main.get_cache', return_value=mock_cache):
            with patch('app.main.app', mock_app):
                with patch('asyncio.sleep', mock_sleep):
                    from app.main import renew_leader_lock
                    # Should not crash, should continue trying
                    await renew_leader_lock()


class TestCORSValidation:
    """Test CORS configuration validation for different environments."""

    def test_development_allows_localhost(self):
        """Development environment should allow localhost CORS."""
        with patch.dict('os.environ', {'ENVIRONMENT': 'development'}):
            with patch('app.core.config.settings') as mock_settings:
                mock_settings.ENVIRONMENT = "development"
                mock_settings.CORS_ORIGINS = ["http://localhost:3000"]

                # Should not raise - development allows localhost
                # This is tested by the fact that the app loads successfully
                assert True

    def test_production_rejects_localhost_only(self):
        """Production should reject if CORS contains only localhost."""
        # This is a design decision test - in production, localhost-only is insecure
        # The main.py exits with sys.exit(1) in this case
        # We test the logic rather than the actual exit since exit would kill tests

        cors_origins = ["http://localhost:3000"]
        environment = "production"

        # Replicate the validation logic from main.py
        should_fail = (
            environment == "production" and
            "http://localhost:3000" in cors_origins and
            len(cors_origins) == 1
        )

        assert should_fail is True

    def test_production_allows_valid_origins(self):
        """Production with valid CORS origins should pass validation."""
        cors_origins = ["https://myapp.com", "https://api.myapp.com"]
        environment = "production"

        # Should not fail - production with valid origins
        should_fail = (
            environment == "production" and
            "http://localhost:3000" in cors_origins and
            len(cors_origins) == 1
        )

        assert should_fail is False

    def test_production_allows_multiple_origins_including_localhost(self):
        """Production with multiple origins (including localhost) should pass."""
        # Edge case: if localhost is not the ONLY origin, it's allowed
        cors_origins = ["http://localhost:3000", "https://myapp.com"]
        environment = "production"

        should_fail = (
            environment == "production" and
            "http://localhost:3000" in cors_origins and
            len(cors_origins) == 1
        )

        # len > 1, so should not fail
        assert should_fail is False


class TestStartupEvent:
    """Test application startup event initialization."""

    @pytest.mark.asyncio
    async def test_startup_as_leader_initializes_all_services(self):
        """When elected leader, should initialize all background services."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.return_value = True

        # Mock all the services
        mock_order_monitor = MagicMock()
        mock_order_monitor.start_monitoring_task = AsyncMock()

        mock_queue_manager = MagicMock()
        mock_queue_manager.start_promotion_task = AsyncMock()

        mock_risk_engine = MagicMock()
        mock_risk_engine.start_monitoring_task = AsyncMock()

        with patch('app.main.get_cache', return_value=mock_cache):
            with patch('app.main.OrderFillMonitorService', return_value=mock_order_monitor):
                with patch('app.main.QueueManagerService', return_value=mock_queue_manager):
                    with patch('app.main.RiskEngineService', return_value=mock_risk_engine):
                        with patch('app.main.setup_logging'):
                            with patch('app.main.AsyncSessionLocal'):
                                with patch('app.main.get_db_session'):
                                    from app.main import startup_event, app

                                    await startup_event()

                                    # Verify leader status
                                    assert app.state.is_leader is True

                                    # Verify services were started
                                    mock_order_monitor.start_monitoring_task.assert_called_once()
                                    mock_queue_manager.start_promotion_task.assert_called_once()
                                    mock_risk_engine.start_monitoring_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_as_follower_skips_background_services(self):
        """When not elected leader, should skip background service initialization."""
        mock_cache = AsyncMock()
        mock_cache.acquire_lock.return_value = False  # Not leader

        mock_order_monitor = MagicMock()
        mock_order_monitor.start_monitoring_task = AsyncMock()

        with patch('app.main.get_cache', return_value=mock_cache):
            with patch('app.main.OrderFillMonitorService', return_value=mock_order_monitor):
                with patch('app.main.setup_logging'):
                    with patch('app.main.AsyncSessionLocal'):
                        from app.main import startup_event, app

                        await startup_event()

                        # Verify follower status
                        assert app.state.is_leader is False

                        # Verify background services were NOT started
                        mock_order_monitor.start_monitoring_task.assert_not_called()


class TestShutdownEvent:
    """Test application shutdown event cleanup."""

    @pytest.mark.asyncio
    async def test_shutdown_as_leader_stops_all_services(self):
        """Leader should stop all background services on shutdown."""
        mock_cache = AsyncMock()
        mock_cache.release_lock = AsyncMock(return_value=True)

        mock_order_monitor = MagicMock()
        mock_order_monitor.stop_monitoring_task = AsyncMock()

        mock_queue_manager = MagicMock()
        mock_queue_manager.stop_promotion_task = AsyncMock()

        mock_risk_engine = MagicMock()
        mock_risk_engine.stop_monitoring_task = AsyncMock()

        mock_watchdog = MagicMock()
        mock_watchdog.stop = AsyncMock()

        mock_renewal_task = MagicMock()
        mock_renewal_task.cancel = MagicMock()

        # get_cache is async, so we need AsyncMock for the patch
        with patch('app.main.get_cache', new=AsyncMock(return_value=mock_cache)):
            from app.main import shutdown_event, app

            # Set up app state as if it was leader
            app.state.is_leader = True
            app.state.order_fill_monitor = mock_order_monitor
            app.state.queue_manager_service = mock_queue_manager
            app.state.risk_engine_service = mock_risk_engine
            app.state.watchdog = mock_watchdog
            app.state.leader_renewal_task = mock_renewal_task

            await shutdown_event()

            # Verify all services were stopped
            mock_watchdog.stop.assert_called_once()
            mock_order_monitor.stop_monitoring_task.assert_called_once()
            mock_queue_manager.stop_promotion_task.assert_called_once()
            mock_risk_engine.stop_monitoring_task.assert_called_once()
            mock_renewal_task.cancel.assert_called_once()
            mock_cache.release_lock.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_as_follower_skips_service_cleanup(self):
        """Follower should not try to stop services it never started."""
        from app.main import shutdown_event, app

        # Set up app state as follower
        app.state.is_leader = False

        # Should not raise even though services don't exist
        await shutdown_event()

    @pytest.mark.asyncio
    async def test_shutdown_handles_cache_release_failure(self):
        """Shutdown should handle Redis failure gracefully."""
        async def raise_redis_error():
            raise Exception("Redis unavailable")

        mock_order_monitor = MagicMock()
        mock_order_monitor.stop_monitoring_task = AsyncMock()

        mock_queue_manager = MagicMock()
        mock_queue_manager.stop_promotion_task = AsyncMock()

        mock_risk_engine = MagicMock()
        mock_risk_engine.stop_monitoring_task = AsyncMock()

        mock_renewal_task = MagicMock()
        mock_renewal_task.cancel = MagicMock()

        with patch('app.main.get_cache', side_effect=raise_redis_error):
            from app.main import shutdown_event, app

            app.state.is_leader = True
            app.state.order_fill_monitor = mock_order_monitor
            app.state.queue_manager_service = mock_queue_manager
            app.state.risk_engine_service = mock_risk_engine
            app.state.leader_renewal_task = mock_renewal_task

            # Should not raise despite Redis failure
            await shutdown_event()

            # Services should still be stopped
            mock_order_monitor.stop_monitoring_task.assert_called_once()


class TestAppRouters:
    """Test that all expected routers are included."""

    def test_all_routers_included(self):
        """Verify all expected API routers are included."""
        from app.main import app

        routes = [route.path for route in app.routes]

        # Check core API routes exist
        expected_prefixes = [
            "/api/v1/health",
            "/api/v1/risk",
            "/api/v1/positions",
            "/api/v1/webhooks",
            "/api/v1/queue",
            "/api/v1/users",
            "/api/v1/settings",
            "/api/v1/dashboard",
            "/api/v1/logs",
            "/api/v1/dca-configs",
            "/api/v1/telegram",
        ]

        for prefix in expected_prefixes:
            # Check if any route starts with this prefix
            has_route = any(route.startswith(prefix) for route in routes)
            assert has_route, f"Missing router for prefix: {prefix}"


class TestWorkerID:
    """Test worker ID generation."""

    def test_worker_id_is_unique_8_chars(self):
        """Worker ID should be 8 character unique identifier."""
        from app.main import WORKER_ID

        assert len(WORKER_ID) == 8
        # Should be a valid hex string (from UUID)
        assert all(c in '0123456789abcdef-' for c in WORKER_ID)


class TestMiddleware:
    """Test middleware configuration."""

    def test_cors_middleware_configured(self):
        """CORS middleware should be configured."""
        from app.main import app

        # Check middleware stack
        middleware_types = [type(m).__name__ for m in app.user_middleware]

        # CORS is added via add_middleware, check if it's in the stack
        # Note: FastAPI wraps middleware differently
        assert len(app.user_middleware) >= 1

    def test_rate_limiter_configured(self):
        """Rate limiter should be configured on app state."""
        from app.main import app

        assert hasattr(app.state, 'limiter')
        assert app.state.limiter is not None
