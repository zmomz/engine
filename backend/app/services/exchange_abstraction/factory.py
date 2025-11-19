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

def get_exchange_connector(exchange_type: str, api_key: str = "", secret_key: str = "", testnet: bool = None, default_type: str = None) -> ExchangeInterface:
    """
    Factory function to get an exchange connector instance.
    """
    if testnet is None:
        testnet = os.getenv("EXCHANGE_TESTNET", "false").lower() == "true"
    
    if default_type is None:
        default_type = os.getenv("EXCHANGE_DEFAULT_TYPE", "future")

    if exchange_type == "mock":
        return MockConnector()
    elif exchange_type == "binance":
        return BinanceConnector(api_key=api_key, secret_key=secret_key, testnet=testnet, default_type=default_type)
    elif exchange_type == "bybit":
        return BybitConnector(api_key=api_key, secret_key=secret_key)
    else:
        raise UnsupportedExchangeError(f"Exchange type '{exchange_type}' is not supported.")
