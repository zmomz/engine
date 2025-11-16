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
