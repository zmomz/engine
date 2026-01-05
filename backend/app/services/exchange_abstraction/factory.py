import os
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.binance_connector import BinanceConnector
from app.services.exchange_abstraction.bybit_connector import BybitConnector
from app.services.exchange_abstraction.mock_connector import MockConnector
from app.core.circuit_breaker import get_exchange_circuit, CircuitBreakerError

logger = logging.getLogger(__name__)

class UnsupportedExchangeError(Exception):
    """
    Custom exception for unsupported exchange types.
    """
    pass

from app.core.security import EncryptionService


# Connector cache with TTL (5 minutes)
# Key: hash of (exchange_type, api_key_prefix, testnet, account_type)
# Value: (connector, created_time)
_connector_cache: Dict[str, Tuple[ExchangeInterface, datetime]] = {}
_cache_lock = asyncio.Lock()
CONNECTOR_CACHE_TTL = timedelta(minutes=5)


def _get_cache_key(exchange_type: str, api_key: str, testnet: bool, account_type: str = None, default_type: str = None) -> str:
    """Generate a cache key for the connector."""
    key_parts = f"{exchange_type}:{api_key[:8]}:{testnet}:{account_type}:{default_type}"
    return hashlib.md5(key_parts.encode()).hexdigest()


async def _cleanup_expired_connectors():
    """Remove expired connectors from cache."""
    global _connector_cache
    now = datetime.utcnow()
    expired_keys = [
        key for key, (_, created_time) in _connector_cache.items()
        if now - created_time > CONNECTOR_CACHE_TTL
    ]
    for key in expired_keys:
        connector, _ = _connector_cache.pop(key, (None, None))
        if connector and hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
            try:
                await connector.exchange.close()
            except Exception:
                pass
        logger.debug(f"Cleaned up expired connector: {key[:8]}...")


def get_exchange_connector(exchange_type: str, exchange_config: dict, use_cache: bool = True) -> ExchangeInterface:
    """
    Factory function to get an exchange connector instance from a configuration dictionary.

    Args:
        exchange_type: The exchange type (binance, bybit, mock)
        exchange_config: Configuration dictionary with encrypted_data and other settings
        use_cache: Whether to use cached connectors (default True). Set False to force new instance.

    Returns:
        ExchangeInterface implementation
    """
    exchange_type = exchange_type.lower()

    # Handle mock exchange separately - no encryption needed, always create new
    if exchange_type == "mock":
        mock_config = {
            "api_key": exchange_config.get("api_key", "mock_api_key_12345"),
            "api_secret": exchange_config.get("api_secret", "mock_api_secret_67890"),
        }
        return MockConnector(config=mock_config)

    # For real exchanges, decrypt keys
    encryption_service = EncryptionService()
    api_key, secret_key = encryption_service.decrypt_keys(exchange_config["encrypted_data"])

    testnet = exchange_config.get("testnet", False)
    account_type = exchange_config.get("account_type", "UNIFIED")
    default_type = exchange_config.get("default_type", "spot")

    # Generate cache key
    cache_key = _get_cache_key(exchange_type, api_key, testnet, account_type, default_type)

    # Check cache if enabled
    if use_cache and cache_key in _connector_cache:
        connector, created_time = _connector_cache[cache_key]
        if datetime.utcnow() - created_time < CONNECTOR_CACHE_TTL:
            logger.debug(f"Reusing cached connector for {exchange_type}")
            return connector
        else:
            # Expired, remove from cache
            _connector_cache.pop(cache_key, None)

    # Create new connector
    if exchange_type == "binance":
        connector = BinanceConnector(api_key=api_key, secret_key=secret_key, testnet=testnet, default_type=default_type)
    elif exchange_type == "bybit":
        connector = BybitConnector(api_key=api_key, secret_key=secret_key, testnet=testnet, default_type=default_type, account_type=account_type)
    else:
        raise UnsupportedExchangeError(f"Exchange type '{exchange_type}' is not supported.")

    # Cache the connector
    if use_cache:
        _connector_cache[cache_key] = (connector, datetime.utcnow())
        logger.debug(f"Cached new connector for {exchange_type}")

    return connector


def get_supported_exchanges() -> list[str]:
    """
    Returns a list of supported exchange IDs.
    """
    return ["binance", "bybit", "mock"]


async def clear_connector_cache():
    """Clear all cached connectors. Call on shutdown."""
    global _connector_cache
    async with _cache_lock:
        for key, (connector, _) in list(_connector_cache.items()):
            if connector and hasattr(connector, 'exchange') and hasattr(connector.exchange, 'close'):
                try:
                    await connector.exchange.close()
                except Exception:
                    pass
        _connector_cache.clear()
        logger.info("Cleared all cached connectors")


async def check_exchange_circuit(exchange_type: str) -> bool:
    """
    Check if an exchange circuit breaker allows requests.

    Args:
        exchange_type: The exchange type (binance, bybit, mock)

    Returns:
        True if requests are allowed, False if circuit is open

    Raises:
        CircuitBreakerError: If circuit is open with details about retry time
    """
    exchange_type = exchange_type.lower()

    # Mock exchange doesn't use circuit breaker
    if exchange_type == "mock":
        return True

    circuit = await get_exchange_circuit(exchange_type)
    return await circuit.can_execute()


async def record_exchange_success(exchange_type: str):
    """
    Record a successful exchange operation.
    Should be called after successful API calls.

    Args:
        exchange_type: The exchange type
    """
    exchange_type = exchange_type.lower()
    if exchange_type == "mock":
        return

    circuit = await get_exchange_circuit(exchange_type)
    await circuit.record_success()


async def record_exchange_failure(exchange_type: str):
    """
    Record a failed exchange operation.
    Should be called after failed API calls.

    Args:
        exchange_type: The exchange type
    """
    exchange_type = exchange_type.lower()
    if exchange_type == "mock":
        return

    circuit = await get_exchange_circuit(exchange_type)
    await circuit.record_failure()


async def get_exchange_circuit_status(exchange_type: str) -> dict:
    """
    Get the circuit breaker status for an exchange.

    Args:
        exchange_type: The exchange type

    Returns:
        Dict with circuit breaker metrics
    """
    exchange_type = exchange_type.lower()
    if exchange_type == "mock":
        return {"name": "mock", "state": "closed", "note": "Mock exchange - no circuit breaker"}

    circuit = await get_exchange_circuit(exchange_type)
    return circuit.get_metrics()


async def reset_exchange_circuit(exchange_type: str):
    """
    Manually reset an exchange circuit breaker to closed state.

    Args:
        exchange_type: The exchange type
    """
    exchange_type = exchange_type.lower()
    if exchange_type == "mock":
        return

    circuit = await get_exchange_circuit(exchange_type)
    await circuit.reset()
    logger.info(f"Manually reset circuit breaker for {exchange_type}")


def get_exchange_connector_with_circuit(
    exchange_type: str,
    exchange_config: dict,
    use_cache: bool = True
) -> Tuple[ExchangeInterface, bool]:
    """
    Get exchange connector with circuit breaker pre-check.

    This is a synchronous wrapper that returns both the connector
    and a flag indicating if the circuit is healthy.

    For full circuit breaker integration, use the async functions
    record_exchange_success/record_exchange_failure after API calls.

    Args:
        exchange_type: The exchange type
        exchange_config: Configuration dictionary
        use_cache: Whether to use cached connectors

    Returns:
        Tuple of (connector, is_circuit_healthy)
    """
    connector = get_exchange_connector(exchange_type, exchange_config, use_cache)

    # Note: Circuit check is async, so we can't do it here synchronously.
    # The caller should use check_exchange_circuit() before making calls.
    # This function just returns the connector for convenience.

    return connector, True
