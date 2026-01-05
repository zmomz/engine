"""
Redis cache service for performance optimization.
Provides caching for:
- Exchange precision rules (24h TTL)
- Dashboard balances (5min TTL)
- Ticker data (1min TTL)
"""
import json
import logging
import os
from typing import Any, Optional
from decimal import Decimal

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def decimal_decoder(dct):
    """Decode dictionaries, converting string numbers back to appropriate types."""
    for key, value in dct.items():
        if isinstance(value, str):
            try:
                # Try to convert to float for numeric strings
                if '.' in value or 'e' in value.lower():
                    dct[key] = float(value)
            except (ValueError, TypeError):
                pass
    return dct


class CacheService:
    """
    Redis-based cache service for the trading engine.
    Falls back gracefully if Redis is unavailable.
    Includes automatic reconnection logic for resilience.
    """

    # TTL constants in seconds
    TTL_PRECISION_RULES = 172800  # 2 days (48 hours)
    TTL_BALANCE = 300  # 5 minutes
    TTL_TICKERS = 5  # 5 seconds - needs to be fresh for position PnL
    TTL_DASHBOARD = 60  # 1 minute
    TTL_DCA_CONFIG = 300  # 5 minutes
    TTL_USER = 300  # 5 minutes

    # Key prefixes
    PREFIX_PRECISION = "precision"
    PREFIX_BALANCE = "balance"
    PREFIX_TICKERS = "tickers"
    PREFIX_DASHBOARD = "dashboard"
    PREFIX_TOKEN_BLACKLIST = "token_blacklist"
    PREFIX_DISTRIBUTED_LOCK = "lock"
    PREFIX_SERVICE_HEALTH = "service_health"
    PREFIX_DCA_CONFIG = "dca_config"
    PREFIX_USER = "user"

    # Reconnection settings
    RECONNECT_INTERVAL = 30  # seconds between reconnection attempts
    MAX_RECONNECT_ATTEMPTS = 3  # max consecutive failures before backing off
    BACKOFF_MULTIPLIER = 2  # exponential backoff multiplier

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        self._connection_attempted = False
        self._redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self._last_reconnect_attempt = 0
        self._consecutive_failures = 0
        self._reconnect_lock = None  # Will be initialized as asyncio.Lock

    async def _get_reconnect_lock(self):
        """Get or create the reconnect lock."""
        if self._reconnect_lock is None:
            import asyncio
            self._reconnect_lock = asyncio.Lock()
        return self._reconnect_lock

    async def connect(self) -> bool:
        """
        Initialize Redis connection.
        Returns True if connected, False otherwise.
        """
        if self._connection_attempted and self._connected:
            return self._connected

        self._connection_attempted = True

        try:
            self._redis = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            self._consecutive_failures = 0
            logger.info(f"Connected to Redis at {self._redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._connected = False
            self._redis = None
            self._consecutive_failures += 1
            return False

    async def _ensure_connected(self) -> bool:
        """
        Ensure Redis connection is alive, attempting reconnection if needed.
        Uses exponential backoff to prevent reconnection storms.
        Returns True if connected, False otherwise.
        """
        if self._connected:
            return True

        import time
        current_time = time.time()

        # Calculate backoff delay based on consecutive failures
        backoff_delay = self.RECONNECT_INTERVAL * (
            self.BACKOFF_MULTIPLIER ** min(self._consecutive_failures, self.MAX_RECONNECT_ATTEMPTS)
        )

        # Check if enough time has passed since last reconnection attempt
        if current_time - self._last_reconnect_attempt < backoff_delay:
            return False

        # Use lock to prevent multiple concurrent reconnection attempts
        lock = await self._get_reconnect_lock()
        if lock.locked():
            return self._connected

        async with lock:
            # Double-check after acquiring lock
            if self._connected:
                return True

            self._last_reconnect_attempt = current_time

            try:
                if self._redis:
                    try:
                        await self._redis.close()
                    except Exception:
                        pass

                self._redis = redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                await self._redis.ping()
                self._connected = True
                self._consecutive_failures = 0
                logger.info(f"Reconnected to Redis at {self._redis_url}")
                return True
            except Exception as e:
                self._consecutive_failures += 1
                logger.warning(
                    f"Redis reconnection attempt failed ({self._consecutive_failures} consecutive failures): {e}"
                )
                self._connected = False
                self._redis = None
                return False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self._connected = False
                self._redis = None

    async def health_check(self) -> dict:
        """
        Perform a health check on the Redis connection.
        Returns a dict with connection status and details.
        """
        result = {
            "connected": self._connected,
            "consecutive_failures": self._consecutive_failures,
            "redis_url": self._redis_url.split("@")[-1] if "@" in self._redis_url else self._redis_url  # Hide password
        }

        if self._connected:
            try:
                await self._redis.ping()
                result["status"] = "healthy"
                result["latency_ms"] = "< 5"
            except Exception as e:
                result["status"] = "unhealthy"
                result["error"] = str(e)
                self._connected = False
        else:
            result["status"] = "disconnected"

        return result

    def _make_key(self, prefix: str, *parts: str) -> str:
        """Create a cache key from prefix and parts."""
        return f"{prefix}:{':'.join(str(p) for p in parts)}"

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache. Attempts reconnection if disconnected."""
        # Try to ensure connection (will attempt reconnect with backoff)
        await self._ensure_connected()

        if not self._connected:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value, object_hook=decimal_decoder)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            # Mark as disconnected for reconnection on next attempt
            self._connected = False
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a value in cache with TTL. Attempts reconnection if disconnected."""
        # Try to ensure connection (will attempt reconnect with backoff)
        await self._ensure_connected()

        if not self._connected:
            return False

        try:
            serialized = json.dumps(value, cls=DecimalEncoder)
            await self._redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            # Mark as disconnected for reconnection on next attempt
            self._connected = False
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache. Attempts reconnection if disconnected."""
        # Try to ensure connection (will attempt reconnect with backoff)
        await self._ensure_connected()

        if not self._connected:
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            # Mark as disconnected for reconnection on next attempt
            self._connected = False
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Attempts reconnection if disconnected."""
        # Try to ensure connection (will attempt reconnect with backoff)
        await self._ensure_connected()

        if not self._connected:
            return 0

        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern failed for {pattern}: {e}")
            # Mark as disconnected for reconnection on next attempt
            self._connected = False
            return 0

    # ==================== Precision Rules ====================

    async def get_precision_rules(self, exchange: str) -> Optional[dict]:
        """Get cached precision rules for an exchange."""
        key = self._make_key(self.PREFIX_PRECISION, exchange.lower())
        return await self.get(key)

    async def set_precision_rules(self, exchange: str, rules: dict) -> bool:
        """Cache precision rules for an exchange (2 days TTL)."""
        key = self._make_key(self.PREFIX_PRECISION, exchange.lower())
        return await self.set(key, rules, self.TTL_PRECISION_RULES)

    async def invalidate_precision_rules(self, exchange: str) -> bool:
        """
        Invalidate cached precision rules for an exchange.
        Call this when a precision-related order error occurs.
        """
        key = self._make_key(self.PREFIX_PRECISION, exchange.lower())
        return await self.delete(key)

    async def get_symbol_precision(self, exchange: str, symbol: str) -> Optional[dict]:
        """
        Get precision rules for a specific symbol.
        Returns None if symbol not found in cache.
        """
        rules = await self.get_precision_rules(exchange)
        if rules:
            return rules.get(symbol)
        return None

    # ==================== Balance ====================

    async def get_balance(self, user_id: str, exchange: str) -> Optional[dict]:
        """Get cached balance for a user on an exchange."""
        key = self._make_key(self.PREFIX_BALANCE, user_id, exchange.lower())
        return await self.get(key)

    async def set_balance(self, user_id: str, exchange: str, balance: dict) -> bool:
        """Cache balance for a user on an exchange (5min TTL)."""
        key = self._make_key(self.PREFIX_BALANCE, user_id, exchange.lower())
        return await self.set(key, balance, self.TTL_BALANCE)

    async def invalidate_user_balances(self, user_id: str) -> int:
        """Invalidate all cached balances for a user."""
        pattern = self._make_key(self.PREFIX_BALANCE, user_id, "*")
        return await self.delete_pattern(pattern)

    # ==================== Tickers ====================

    async def get_tickers(self, exchange: str) -> Optional[dict]:
        """Get cached tickers for an exchange."""
        key = self._make_key(self.PREFIX_TICKERS, exchange.lower())
        return await self.get(key)

    async def set_tickers(self, exchange: str, tickers: dict) -> bool:
        """Cache tickers for an exchange (1min TTL)."""
        key = self._make_key(self.PREFIX_TICKERS, exchange.lower())
        return await self.set(key, tickers, self.TTL_TICKERS)

    # ==================== Dashboard ====================

    async def get_dashboard(self, user_id: str, endpoint: str) -> Optional[dict]:
        """Get cached dashboard data for a user."""
        key = self._make_key(self.PREFIX_DASHBOARD, user_id, endpoint)
        return await self.get(key)

    async def set_dashboard(self, user_id: str, endpoint: str, data: dict) -> bool:
        """Cache dashboard data for a user (1min TTL)."""
        key = self._make_key(self.PREFIX_DASHBOARD, user_id, endpoint)
        return await self.set(key, data, self.TTL_DASHBOARD)

    async def invalidate_user_dashboard(self, user_id: str) -> int:
        """Invalidate all cached dashboard data for a user."""
        pattern = self._make_key(self.PREFIX_DASHBOARD, user_id, "*")
        return await self.delete_pattern(pattern)

    # ==================== DCA Config ====================

    async def get_dca_config(
        self,
        user_id: str,
        pair: str,
        timeframe: str,
        exchange: str
    ) -> Optional[dict]:
        """Get cached DCA configuration."""
        key = self._make_key(self.PREFIX_DCA_CONFIG, user_id, exchange, pair, timeframe)
        return await self.get(key)

    async def set_dca_config(
        self,
        user_id: str,
        pair: str,
        timeframe: str,
        exchange: str,
        config: dict
    ) -> bool:
        """Cache DCA configuration (5min TTL)."""
        key = self._make_key(self.PREFIX_DCA_CONFIG, user_id, exchange, pair, timeframe)
        return await self.set(key, config, self.TTL_DCA_CONFIG)

    async def invalidate_user_dca_configs(self, user_id: str) -> int:
        """Invalidate all cached DCA configs for a user."""
        pattern = self._make_key(self.PREFIX_DCA_CONFIG, user_id, "*")
        return await self.delete_pattern(pattern)

    # ==================== Token Blacklist ====================

    async def blacklist_token(self, jti: str, ttl_seconds: int) -> bool:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID (unique identifier for the token)
            ttl_seconds: Time until token expires (blacklist entry auto-removes after)
        """
        if not self._connected:
            return False

        try:
            key = self._make_key(self.PREFIX_TOKEN_BLACKLIST, jti)
            await self._redis.setex(key, ttl_seconds, "1")
            return True
        except Exception as e:
            logger.warning(f"Token blacklist failed for {jti}: {e}")
            return False

    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if a token is blacklisted."""
        if not self._connected:
            return False

        try:
            key = self._make_key(self.PREFIX_TOKEN_BLACKLIST, jti)
            result = await self._redis.exists(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Token blacklist check failed for {jti}: {e}")
            return False

    # ==================== Distributed Locking ====================

    async def acquire_lock(
        self,
        resource: str,
        lock_id: str,
        ttl_seconds: int = 30
    ) -> bool:
        """
        Acquire a distributed lock for a resource.
        Attempts reconnection if disconnected.

        Args:
            resource: The resource to lock (e.g., "webhook:user123:BTCUSDT:15")
            lock_id: Unique identifier for this lock attempt
            ttl_seconds: Lock timeout to prevent deadlocks

        Returns:
            True if lock acquired, False otherwise
        """
        # Try to ensure connection (will attempt reconnect with backoff)
        await self._ensure_connected()

        if not self._connected:
            return True  # Fallback to no-lock if Redis unavailable

        try:
            key = self._make_key(self.PREFIX_DISTRIBUTED_LOCK, resource)
            # SET NX (only set if not exists) with expiry
            result = await self._redis.set(key, lock_id, nx=True, ex=ttl_seconds)
            return result is not None
        except Exception as e:
            logger.warning(f"Lock acquisition failed for {resource}: {e}")
            self._connected = False
            return True  # Fallback to allowing operation

    async def release_lock(self, resource: str, lock_id: str) -> bool:
        """
        Release a distributed lock.
        Attempts reconnection if disconnected.

        Args:
            resource: The resource to unlock
            lock_id: The lock ID used when acquiring (only release if it matches)

        Returns:
            True if lock released, False otherwise
        """
        # Try to ensure connection (will attempt reconnect with backoff)
        await self._ensure_connected()

        if not self._connected:
            return True

        try:
            key = self._make_key(self.PREFIX_DISTRIBUTED_LOCK, resource)
            # Only delete if the lock_id matches (prevent releasing others' locks)
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = await self._redis.eval(lua_script, 1, key, lock_id)
            return result == 1
        except Exception as e:
            logger.warning(f"Lock release failed for {resource}: {e}")
            self._connected = False
            return False

    # ==================== Service Health ====================

    async def update_service_health(
        self,
        service_name: str,
        status: str,
        metrics: dict = None
    ) -> bool:
        """
        Update health status for a background service.

        Args:
            service_name: Name of the service (e.g., "order_fill_monitor")
            status: Current status ("running", "error", "stopped")
            metrics: Optional metrics dict (cycle_count, last_error, etc.)
        """
        if not self._connected:
            return False

        try:
            import time
            key = self._make_key(self.PREFIX_SERVICE_HEALTH, service_name)
            health_data = {
                "status": status,
                "last_heartbeat": time.time(),
                "metrics": metrics or {}
            }
            # Use 5 minute TTL - if not updated, service is considered unhealthy
            await self._redis.setex(key, 300, json.dumps(health_data, cls=DecimalEncoder))
            return True
        except Exception as e:
            logger.warning(f"Service health update failed for {service_name}: {e}")
            return False

    async def get_service_health(self, service_name: str) -> Optional[dict]:
        """Get health status for a service."""
        if not self._connected:
            return None

        try:
            key = self._make_key(self.PREFIX_SERVICE_HEALTH, service_name)
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Service health get failed for {service_name}: {e}")
            return None

    async def get_all_services_health(self) -> dict:
        """Get health status for all services."""
        if not self._connected:
            return {}

        try:
            pattern = self._make_key(self.PREFIX_SERVICE_HEALTH, "*")
            result = {}
            async for key in self._redis.scan_iter(match=pattern):
                service_name = key.split(":")[-1]
                value = await self._redis.get(key)
                if value:
                    result[service_name] = json.loads(value)
            return result
        except Exception as e:
            logger.warning(f"Get all services health failed: {e}")
            return {}


# Global cache instance
_cache_instance: Optional[CacheService] = None


async def get_cache() -> CacheService:
    """Get the global cache instance, initializing if needed."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
        await _cache_instance.connect()
    return _cache_instance


async def close_cache():
    """Close the global cache instance."""
    global _cache_instance
    if _cache_instance:
        await _cache_instance.close()
        _cache_instance = None
