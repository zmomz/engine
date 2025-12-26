import os
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.binance_connector import BinanceConnector
from app.services.exchange_abstraction.bybit_connector import BybitConnector
from app.services.exchange_abstraction.mock_connector import MockConnector

class UnsupportedExchangeError(Exception):
    """
    Custom exception for unsupported exchange types.
    """
    pass

from app.core.security import EncryptionService

def get_exchange_connector(exchange_type: str, exchange_config: dict) -> ExchangeInterface:
    """
    Factory function to get an exchange connector instance from a configuration dictionary.
    """
    exchange_type = exchange_type.lower()

    # Handle mock exchange separately - no encryption needed
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
    account_type = exchange_config.get("account_type", "UNIFIED") # Default to UNIFIED for Bybit if not specified
    default_type = exchange_config.get("default_type", "spot") # Default to spot for Binance if not specified

    if exchange_type == "binance":
        return BinanceConnector(api_key=api_key, secret_key=secret_key, testnet=testnet, default_type=default_type)
    elif exchange_type == "bybit":
        return BybitConnector(api_key=api_key, secret_key=secret_key, testnet=testnet, default_type=default_type, account_type=account_type)
    else:
        raise UnsupportedExchangeError(f"Exchange type '{exchange_type}' is not supported.")

def get_supported_exchanges() -> list[str]:
    """
    Returns a list of supported exchange IDs.
    """
    return ["binance", "bybit", "mock"]
