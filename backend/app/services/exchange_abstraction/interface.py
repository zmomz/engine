from abc import ABC, abstractmethod

class ExchangeInterface(ABC):
    """
    Abstract base class for exchange connectors.
    """
    @abstractmethod
    async def get_precision_rules(self):
        pass

    @abstractmethod
    async def place_order(self, symbol: str, order_type: str, side: str, quantity: float, price: float = None, **kwargs):
        pass

    @abstractmethod
    async def get_order_status(self):
        """
        Fetches the status of a specific order by its ID.
        Must return a dictionary containing at least 'id', 'status', 'filled', and 'price'.
        """
        pass

    @abstractmethod
    async def cancel_order(self):
        pass

    @abstractmethod
    async def get_current_price(self):
        pass

    @abstractmethod
    async def get_all_tickers(self):
        """
        Fetches all tickers from the exchange.
        Returns a dictionary where keys are symbols and values are ticker data (including 'last' price).
        """
        pass

    @abstractmethod
    async def fetch_balance(self):
        pass

    @abstractmethod
    async def fetch_free_balance(self):
        """
        Fetches the free (available) balance for all assets.
        """
        pass

    @abstractmethod
    async def close(self):
        """
        Closes the exchange connection and releases resources.
        """
        pass

    @abstractmethod
    async def get_trading_fee_rate(self, symbol: str = None) -> float:
        """
        Fetches the trading fee rate for a symbol (taker fee as decimal).
        Returns 0.001 (0.1%) as default if exchange doesn't support fee fetching.

        Args:
            symbol: Trading pair (optional, some exchanges return account-level fees)

        Returns:
            Fee rate as decimal (e.g., 0.001 for 0.1%)
        """
        pass
