from app.services.exchange_abstraction.interface import ExchangeInterface
from app.services.exchange_abstraction.binance_connector import BinanceConnector
from app.services.exchange_abstraction.bybit_connector import BybitConnector
from app.services.exchange_abstraction.mock_connector import MockConnector

class UnsupportedExchangeError(Exception):
    """
    Custom exception for unsupported exchange types.
    """
    pass

def get_exchange_connector(exchange_type: str, api_key: str = "", secret_key: str = "") -> ExchangeInterface:
    """
    Factory function to get an exchange connector instance.
    """
    if exchange_type == "mock":
        return MockConnector()
    elif exchange_type == "binance":
        return BinanceConnector(api_key=api_key, secret_key=secret_key)
    elif exchange_type == "bybit":
        return BybitConnector(api_key=api_key, secret_key=secret_key)
    else:
        raise UnsupportedExchangeError(f"Exchange type '{exchange_type}' is not supported.")
