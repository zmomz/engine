from abc import ABC, abstractmethod

class ExchangeInterface(ABC):
    """
    Abstract base class for exchange connectors.
    """
    @abstractmethod
    async def get_precision_rules(self):
        pass

    @abstractmethod
    async def place_order(self):
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
    async def fetch_balance(self):
        pass

    @abstractmethod
    async def close(self):
        """
        Closes the exchange connection and releases resources.
        """
        pass
