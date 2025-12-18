class APIError(Exception):
    """
    Base exception for all API-related errors.
    """
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class InvalidCredentialsError(APIError):
    """
    Exchange API credentials error (not JWT auth failure).
    Uses 403 to distinguish from 401 which is reserved for JWT/session auth failures.
    This prevents the frontend from logging out the user when exchange API keys are invalid.
    """
    def __init__(self, message: str = "Invalid Exchange API Credentials.", status_code: int = 403):
        super().__init__(message, status_code)

class InsufficientFundsError(APIError):
    def __init__(self, message: str = "Insufficient funds on the exchange to place the order.", status_code: int = 400):
        super().__init__(message, status_code)

class OrderValidationError(APIError):
    def __init__(self, message: str = "Order validation failed.", status_code: int = 400):
        super().__init__(message, status_code)

class RateLimitError(APIError):
    def __init__(self, message: str = "Approaching exchange rate limits. Throttling requests.", status_code: int = 429):
        super().__init__(message, status_code)

class ExchangeConnectionError(APIError):
    def __init__(self, message: str = "Cannot connect to the exchange. Retrying...", status_code: int = 503):
        super().__init__(message, status_code)

class GenericExchangeError(APIError):
    def __init__(self, message: str = "An unknown exchange error occurred.", status_code: int = 500):
        super().__init__(message, status_code)

class SlippageExceededError(APIError):
    """
    Raised when slippage on a market order exceeds the configured maximum threshold.
    Note: The order has already executed when this is raised (post-execution check).
    """
    def __init__(self, message: str = "Slippage exceeded maximum threshold.", status_code: int = 400):
        super().__init__(message, status_code)
