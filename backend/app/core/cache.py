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
    """

    # TTL constants in seconds
    TTL_PRECISION_RULES = 86400  # 24 hours
    TTL_BALANCE = 300  # 5 minutes
    TTL_TICKERS = 60  # 1 minute
    TTL_DASHBOARD = 60  # 1 minute

    # Key prefixes
    PREFIX_PRECISION = "precision"
    PREFIX_BALANCE = "balance"
    PREFIX_TICKERS = "tickers"
    PREFIX_DASHBOARD = "dashboard"

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        self._connection_attempted = False

    async def connect(self) -> bool:
        """
        Initialize Redis connection.
        Returns True if connected, False otherwise.
        """
        if self._connection_attempted:
            return self._connected

        self._connection_attempted = True
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

        try:
            self._redis = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            self._connected = False
            self._redis = None
            return False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._connected = False

    def _make_key(self, prefix: str, *parts: str) -> str:
        """Create a cache key from prefix and parts."""
        return f"{prefix}:{':'.join(str(p) for p in parts)}"

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self._connected:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value, object_hook=decimal_decoder)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a value in cache with TTL."""
        if not self._connected:
            return False

        try:
            serialized = json.dumps(value, cls=DecimalEncoder)
            await self._redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self._connected:
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
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
            return 0

    # ==================== Precision Rules ====================

    async def get_precision_rules(self, exchange: str) -> Optional[dict]:
        """Get cached precision rules for an exchange."""
        key = self._make_key(self.PREFIX_PRECISION, exchange.lower())
        return await self.get(key)

    async def set_precision_rules(self, exchange: str, rules: dict) -> bool:
        """Cache precision rules for an exchange (24h TTL)."""
        key = self._make_key(self.PREFIX_PRECISION, exchange.lower())
        return await self.set(key, rules, self.TTL_PRECISION_RULES)

    async def invalidate_precision_rules(self, exchange: str) -> bool:
        """Invalidate cached precision rules for an exchange."""
        key = self._make_key(self.PREFIX_PRECISION, exchange.lower())
        return await self.delete(key)

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
