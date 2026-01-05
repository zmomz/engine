"""
Distributed locking utilities for multi-worker deployments.
Provides Redis-based distributed locks that work across multiple processes.
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class DistributedLockManager:
    """
    Manages distributed locks using Redis.
    Provides context manager interface for easy lock acquisition and release.
    Falls back to in-memory locks if Redis is unavailable.
    """

    # Default TTL for position locks (in seconds)
    DEFAULT_LOCK_TTL = 30

    # Maximum time to wait for lock acquisition (in seconds)
    DEFAULT_ACQUIRE_TIMEOUT = 10

    # Retry interval when waiting for lock (in seconds)
    RETRY_INTERVAL = 0.1

    def __init__(self):
        self._fallback_locks: dict[str, asyncio.Lock] = {}
        self._fallback_locks_lock = asyncio.Lock()
        self._active_locks: dict[str, str] = {}  # resource -> lock_id mapping

    async def _get_cache(self):
        """Get the cache service instance."""
        from app.core.cache import get_cache
        return await get_cache()

    async def _get_fallback_lock(self, resource: str) -> asyncio.Lock:
        """Get or create a fallback asyncio lock for a resource."""
        async with self._fallback_locks_lock:
            if resource not in self._fallback_locks:
                self._fallback_locks[resource] = asyncio.Lock()
            return self._fallback_locks[resource]

    async def _cleanup_fallback_lock(self, resource: str):
        """Remove a fallback lock when no longer needed."""
        async with self._fallback_locks_lock:
            if resource in self._fallback_locks:
                del self._fallback_locks[resource]

    async def acquire(
        self,
        resource: str,
        ttl: int = DEFAULT_LOCK_TTL,
        timeout: float = DEFAULT_ACQUIRE_TIMEOUT,
        lock_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Acquire a distributed lock for a resource.

        Args:
            resource: The resource identifier to lock (e.g., "position:uuid")
            ttl: Lock time-to-live in seconds (auto-releases after this time)
            timeout: Maximum time to wait for lock acquisition
            lock_id: Optional custom lock ID (auto-generated if not provided)

        Returns:
            Tuple of (success: bool, lock_id: str)
        """
        if lock_id is None:
            lock_id = str(uuid.uuid4())

        cache = await self._get_cache()

        # If Redis is available, use distributed locking
        if cache._connected:
            start_time = asyncio.get_event_loop().time()

            while True:
                acquired = await cache.acquire_lock(resource, lock_id, ttl)

                if acquired:
                    self._active_locks[resource] = lock_id
                    logger.debug(f"Acquired distributed lock for {resource} with lock_id {lock_id[:8]}")
                    return True, lock_id

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Timeout waiting for distributed lock on {resource} after {elapsed:.2f}s")
                    return False, lock_id

                # Wait before retry
                await asyncio.sleep(self.RETRY_INTERVAL)
        else:
            # Fallback to in-memory lock
            logger.debug(f"Redis unavailable, using fallback lock for {resource}")
            fallback_lock = await self._get_fallback_lock(resource)

            try:
                acquired = await asyncio.wait_for(
                    fallback_lock.acquire(),
                    timeout=timeout
                )
                if acquired:
                    self._active_locks[resource] = lock_id
                    return True, lock_id
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for fallback lock on {resource}")
                return False, lock_id

        return False, lock_id

    async def release(self, resource: str, lock_id: str) -> bool:
        """
        Release a distributed lock.

        Args:
            resource: The resource identifier
            lock_id: The lock ID returned from acquire()

        Returns:
            True if lock was released successfully
        """
        cache = await self._get_cache()

        # Remove from active locks tracking
        if resource in self._active_locks:
            del self._active_locks[resource]

        if cache._connected:
            released = await cache.release_lock(resource, lock_id)
            if released:
                logger.debug(f"Released distributed lock for {resource}")
            else:
                logger.warning(f"Failed to release distributed lock for {resource} (may have expired)")
            return released
        else:
            # Release fallback lock
            async with self._fallback_locks_lock:
                if resource in self._fallback_locks:
                    lock = self._fallback_locks[resource]
                    if lock.locked():
                        lock.release()
                    logger.debug(f"Released fallback lock for {resource}")
                    return True
            return False

    async def extend(self, resource: str, lock_id: str, ttl: int = DEFAULT_LOCK_TTL) -> bool:
        """
        Extend the TTL of an existing lock.

        Args:
            resource: The resource identifier
            lock_id: The lock ID to extend
            ttl: New TTL in seconds

        Returns:
            True if lock was extended successfully
        """
        cache = await self._get_cache()

        if not cache._connected:
            return True  # Fallback locks don't expire

        try:
            key = cache._make_key(cache.PREFIX_DISTRIBUTED_LOCK, resource)

            # Only extend if we still own the lock
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            result = await cache._redis.eval(lua_script, 1, key, lock_id, ttl)

            if result == 1:
                logger.debug(f"Extended lock TTL for {resource} by {ttl}s")
                return True
            else:
                logger.warning(f"Failed to extend lock for {resource} (lock not owned)")
                return False
        except Exception as e:
            logger.error(f"Error extending lock for {resource}: {e}")
            return False

    @asynccontextmanager
    async def lock(
        self,
        resource: str,
        ttl: int = DEFAULT_LOCK_TTL,
        timeout: float = DEFAULT_ACQUIRE_TIMEOUT
    ):
        """
        Context manager for acquiring and releasing a distributed lock.

        Usage:
            async with lock_manager.lock("position:uuid"):
                # do work

        Args:
            resource: The resource identifier to lock
            ttl: Lock time-to-live in seconds
            timeout: Maximum time to wait for lock acquisition

        Raises:
            asyncio.TimeoutError: If lock cannot be acquired within timeout
        """
        acquired, lock_id = await self.acquire(resource, ttl, timeout)

        if not acquired:
            raise asyncio.TimeoutError(f"Could not acquire lock for {resource} within {timeout}s")

        try:
            yield lock_id
        finally:
            await self.release(resource, lock_id)

    async def cleanup(self, resource: str):
        """
        Clean up lock resources for a resource that is no longer needed.
        Call this when a position is closed to prevent memory leaks.

        Args:
            resource: The resource identifier to clean up
        """
        # Remove from active locks
        if resource in self._active_locks:
            lock_id = self._active_locks[resource]
            await self.release(resource, lock_id)

        # Clean up fallback lock
        await self._cleanup_fallback_lock(resource)

        logger.debug(f"Cleaned up lock resources for {resource}")

    def get_active_locks_count(self) -> int:
        """Get the number of currently active locks."""
        return len(self._active_locks)


# Global lock manager instance
_lock_manager: Optional[DistributedLockManager] = None


def get_lock_manager() -> DistributedLockManager:
    """Get the global lock manager instance."""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = DistributedLockManager()
    return _lock_manager
