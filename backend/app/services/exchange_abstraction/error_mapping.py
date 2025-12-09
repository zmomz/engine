import ccxt
import ssl
import asyncio
from functools import wraps
from aiohttp.client_exceptions import ClientConnectionError

from app.exceptions import (
    InvalidCredentialsError,
    InsufficientFundsError,
    OrderValidationError,
    RateLimitError,
    ExchangeConnectionError,
    GenericExchangeError,
    APIError
)

# Mapping of ccxt exceptions to our custom application exceptions
CCXT_ERROR_MAP = {
    ccxt.AuthenticationError: InvalidCredentialsError,
    ccxt.InsufficientFunds: InsufficientFundsError,
    ccxt.InvalidOrder: OrderValidationError,
    ccxt.RateLimitExceeded: RateLimitError,
    ccxt.NetworkError: ExchangeConnectionError,
    ccxt.RequestTimeout: ExchangeConnectionError,
    ccxt.ExchangeError: GenericExchangeError,
}

def map_exchange_errors(func):
    """
    Decorator to catch ccxt exceptions and re-raise them as custom APIError exceptions.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ccxt.ExchangeError as e:
            for ccxt_exception, app_exception in CCXT_ERROR_MAP.items():
                if isinstance(e, ccxt_exception):
                    raise app_exception(f"{app_exception().message} Original error: {e}") from e
            # Fallback for any unmapped ccxt.ExchangeError
            raise GenericExchangeError(f"An unexpected exchange error occurred: {e}") from e
        except Exception as e:
            # Catch any other unexpected exceptions and wrap them in a generic APIError
            raise APIError(f"An unexpected application error occurred: {e}") from e
    return wrapper
