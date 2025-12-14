import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.services.exchange_abstraction.interface import ExchangeInterface

class PrecisionService:
    """
    Service for fetching and caching exchange precision rules.

    Supports configurable cache TTL via precision.refresh_seconds in RiskEngineConfig.
    """
    def __init__(
        self,
        exchange_connector: ExchangeInterface,
        cache_ttl_seconds: int = 3600,
        cache_ttl_minutes: int = None  # Deprecated, kept for backward compatibility
    ):
        self.exchange_connector = exchange_connector
        self._cache: Dict[str, Any] = {}
        self._last_fetched: Optional[datetime] = None

        # Support both new seconds-based and legacy minutes-based TTL
        if cache_ttl_minutes is not None:
            self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        else:
            self.cache_ttl = timedelta(seconds=cache_ttl_seconds)

    async def fetch_and_cache_precision_rules(self) -> Dict[str, Any]:
        """
        Fetches precision rules from the exchange and caches them.
        """
        precision_rules = await self.exchange_connector.get_precision_rules()
        self._cache = precision_rules
        self._last_fetched = datetime.utcnow()
        return self._cache

    async def get_precision_rules(self, force_fetch: bool = False) -> Dict[str, Any]:
        """
        Retrieves precision rules from the cache, fetching if stale or forced.
        """
        if force_fetch or not self._last_fetched or (datetime.utcnow() - self._last_fetched > self.cache_ttl):
            return await self.fetch_and_cache_precision_rules()
        return self._cache
