"""
Exchange Configuration Service

Centralized logic for extracting and validating exchange configurations from user credentials.
This eliminates duplicated code across signal_router, positions, risk_engine, and dashboard.
"""

import logging
from typing import Optional, Dict, Any, Tuple

from app.models.user import User
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.exchange_abstraction.interface import ExchangeInterface

logger = logging.getLogger(__name__)


class ExchangeConfigError(Exception):
    """Raised when exchange configuration is invalid or missing."""
    pass


class ExchangeConfigService:
    """
    Service for extracting and validating exchange configurations from user credentials.

    Handles both legacy single-key format and new multi-exchange format.
    """

    @staticmethod
    def get_exchange_config(
        user: User,
        target_exchange: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Extract exchange configuration for a specific exchange.

        Args:
            user: The user model with encrypted_api_keys
            target_exchange: The exchange to get config for (required).

        Returns:
            Tuple of (exchange_name, exchange_config_dict)

        Raises:
            ExchangeConfigError: If no valid configuration is found
        """
        if not user.encrypted_api_keys:
            raise ExchangeConfigError("No API keys configured for this user.")

        if not target_exchange:
            raise ExchangeConfigError("Target exchange must be specified.")

        exchange_name = target_exchange.lower()
        encrypted_keys_map = user.encrypted_api_keys

        if not isinstance(encrypted_keys_map, dict):
            raise ExchangeConfigError("Invalid API keys format.")

        exchange_config = None

        # Try to find config for the target exchange
        if exchange_name in encrypted_keys_map:
            exchange_config = encrypted_keys_map[exchange_name]

        if not exchange_config:
            raise ExchangeConfigError(
                f"No API keys configured for exchange: {exchange_name}"
            )

        # Normalize the config format
        if isinstance(exchange_config, str):
            # Legacy format: just the encrypted string
            exchange_config = {"encrypted_data": exchange_config}
        elif isinstance(exchange_config, dict):
            if "encrypted_data" not in exchange_config:
                raise ExchangeConfigError(
                    f"Invalid configuration for exchange {exchange_name}: missing encrypted_data"
                )
        else:
            raise ExchangeConfigError(
                f"Invalid configuration type for exchange {exchange_name}"
            )

        return exchange_name, exchange_config

    @staticmethod
    def get_connector(
        user: User,
        target_exchange: Optional[str] = None
    ) -> ExchangeInterface:
        """
        Get an initialized exchange connector for the user.

        Args:
            user: The user model with encrypted_api_keys
            target_exchange: The exchange to connect to (required).

        Returns:
            Initialized ExchangeInterface

        Raises:
            ExchangeConfigError: If configuration is invalid
            Exception: If connector initialization fails
        """
        exchange_name, exchange_config = ExchangeConfigService.get_exchange_config(
            user, target_exchange
        )

        return get_exchange_connector(
            exchange_type=exchange_name,
            exchange_config=exchange_config
        )

    @staticmethod
    def get_all_configured_exchanges(user: User) -> Dict[str, Dict[str, Any]]:
        """
        Get all exchange configurations for a user.

        Args:
            user: The user model with encrypted_api_keys

        Returns:
            Dictionary mapping exchange names to their configs
        """
        if not user.encrypted_api_keys:
            return {}

        encrypted_keys_map = user.encrypted_api_keys
        if not isinstance(encrypted_keys_map, dict):
            return {}

        result = {}

        for key, value in encrypted_keys_map.items():
            # Multi-exchange format
            if isinstance(value, str):
                result[key.lower()] = {"encrypted_data": value}
            elif isinstance(value, dict) and "encrypted_data" in value:
                result[key.lower()] = value

        return result

    @staticmethod
    def has_valid_config(user: User, exchange: Optional[str] = None) -> bool:
        """
        Check if user has valid configuration for an exchange.

        Args:
            user: The user model
            exchange: Specific exchange to check, or None for any

        Returns:
            True if valid configuration exists
        """
        try:
            if exchange:
                ExchangeConfigService.get_exchange_config(user, exchange)
            else:
                configs = ExchangeConfigService.get_all_configured_exchanges(user)
                return len(configs) > 0
            return True
        except ExchangeConfigError:
            return False
