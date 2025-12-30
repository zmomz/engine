"""
Comprehensive tests for services/exchange_config_service.py to achieve 100% coverage.
"""
import pytest
from unittest.mock import MagicMock, patch
import uuid

from app.services.exchange_config_service import (
    ExchangeConfigService,
    ExchangeConfigError
)
from app.models.user import User


@pytest.fixture
def mock_user():
    """Create a mock user with various API key configurations."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    # Note: User model no longer has 'exchange' field
    return user


# --- Tests for get_exchange_config ---

def test_get_exchange_config_no_api_keys(mock_user):
    """Test get_exchange_config when user has no API keys."""
    mock_user.encrypted_api_keys = None

    with pytest.raises(ExchangeConfigError, match="No API keys configured"):
        ExchangeConfigService.get_exchange_config(mock_user)


def test_get_exchange_config_invalid_format(mock_user):
    """Test get_exchange_config with invalid format (not dict)."""
    mock_user.encrypted_api_keys = "just_a_string"  # Not a dict

    with pytest.raises(ExchangeConfigError, match="Invalid API keys format"):
        ExchangeConfigService.get_exchange_config(mock_user, "binance")


def test_get_exchange_config_multi_exchange_format(mock_user):
    """Test get_exchange_config with multi-exchange format."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"},
        "bybit": {"encrypted_data": "bybit_key"}
    }

    exchange_name, config = ExchangeConfigService.get_exchange_config(mock_user, "binance")

    assert exchange_name == "binance"
    assert config == {"encrypted_data": "binance_key"}


def test_get_exchange_config_target_exchange(mock_user):
    """Test get_exchange_config with specific target exchange."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"},
        "bybit": {"encrypted_data": "bybit_key"}
    }

    exchange_name, config = ExchangeConfigService.get_exchange_config(mock_user, "bybit")

    assert exchange_name == "bybit"
    assert config == {"encrypted_data": "bybit_key"}


def test_get_exchange_config_requires_target_exchange(mock_user):
    """Test get_exchange_config raises error when target_exchange not specified."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    with pytest.raises(ExchangeConfigError, match="Target exchange must be specified"):
        ExchangeConfigService.get_exchange_config(mock_user)


def test_get_exchange_config_with_target_exchange(mock_user):
    """Test get_exchange_config with explicit target exchange."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    exchange_name, config = ExchangeConfigService.get_exchange_config(mock_user, "binance")

    assert exchange_name == "binance"
    assert config == {"encrypted_data": "binance_key"}


def test_get_exchange_config_exchange_not_in_config(mock_user):
    """Test get_exchange_config when requested exchange not in config."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    # Requesting bybit but only binance config exists
    with pytest.raises(ExchangeConfigError, match="No API keys configured for exchange: bybit"):
        ExchangeConfigService.get_exchange_config(mock_user, "bybit")


def test_get_exchange_config_exchange_not_found(mock_user):
    """Test get_exchange_config when exchange not found."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    with pytest.raises(ExchangeConfigError, match="No API keys configured for exchange: kraken"):
        ExchangeConfigService.get_exchange_config(mock_user, "kraken")


def test_get_exchange_config_normalize_string_config(mock_user):
    """Test get_exchange_config normalizes string config to dict."""
    mock_user.encrypted_api_keys = {
        "binance": "just_a_string_key"  # Legacy format within multi-exchange
    }

    exchange_name, config = ExchangeConfigService.get_exchange_config(mock_user, "binance")

    assert exchange_name == "binance"
    assert config == {"encrypted_data": "just_a_string_key"}


def test_get_exchange_config_missing_encrypted_data(mock_user):
    """Test get_exchange_config when config dict is missing encrypted_data."""
    mock_user.encrypted_api_keys = {
        "binance": {"api_key": "key", "secret": "secret"}  # Missing encrypted_data
    }

    with pytest.raises(ExchangeConfigError, match="missing encrypted_data"):
        ExchangeConfigService.get_exchange_config(mock_user, "binance")


def test_get_exchange_config_invalid_config_type(mock_user):
    """Test get_exchange_config with invalid config type for exchange."""
    mock_user.encrypted_api_keys = {
        "binance": 12345  # Invalid type
    }

    with pytest.raises(ExchangeConfigError, match="Invalid configuration type"):
        ExchangeConfigService.get_exchange_config(mock_user, "binance")


def test_get_exchange_config_case_insensitive(mock_user):
    """Test get_exchange_config normalizes exchange name to lowercase."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    # Uppercase should work
    exchange_name, config = ExchangeConfigService.get_exchange_config(mock_user, "BINANCE")

    assert exchange_name == "binance"
    assert config == {"encrypted_data": "binance_key"}


def test_get_exchange_config_mixed_case(mock_user):
    """Test get_exchange_config with mixed case exchange name."""
    mock_user.encrypted_api_keys = {
        "bybit": {"encrypted_data": "bybit_key"}
    }

    exchange_name, config = ExchangeConfigService.get_exchange_config(mock_user, "ByBit")

    assert exchange_name == "bybit"
    assert config == {"encrypted_data": "bybit_key"}


# --- Tests for get_connector ---

def test_get_connector_success(mock_user):
    """Test get_connector returns initialized connector."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    with patch("app.services.exchange_config_service.get_exchange_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_get_connector.return_value = mock_connector

        result = ExchangeConfigService.get_connector(mock_user, "binance")

        assert result == mock_connector
        mock_get_connector.assert_called_once_with(
            exchange_type="binance",
            exchange_config={"encrypted_data": "binance_key"}
        )


def test_get_connector_invalid_config(mock_user):
    """Test get_connector raises error with invalid config."""
    mock_user.encrypted_api_keys = None

    with pytest.raises(ExchangeConfigError):
        ExchangeConfigService.get_connector(mock_user)


def test_get_connector_requires_target_exchange(mock_user):
    """Test get_connector raises error when target_exchange not specified."""
    mock_user.encrypted_api_keys = {
        "bybit": {"encrypted_data": "bybit_key"}
    }

    with pytest.raises(ExchangeConfigError, match="Target exchange must be specified"):
        ExchangeConfigService.get_connector(mock_user)


# --- Tests for get_all_configured_exchanges ---

def test_get_all_configured_exchanges_no_keys(mock_user):
    """Test get_all_configured_exchanges with no API keys."""
    mock_user.encrypted_api_keys = None

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert result == {}


def test_get_all_configured_exchanges_invalid_format(mock_user):
    """Test get_all_configured_exchanges with invalid format."""
    mock_user.encrypted_api_keys = "not_a_dict"

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert result == {}


def test_get_all_configured_exchanges_multi_exchange(mock_user):
    """Test get_all_configured_exchanges with multi-exchange format."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"},
        "bybit": {"encrypted_data": "bybit_key"}
    }

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert "binance" in result
    assert "bybit" in result
    assert result["binance"] == {"encrypted_data": "binance_key"}
    assert result["bybit"] == {"encrypted_data": "bybit_key"}


def test_get_all_configured_exchanges_single_exchange(mock_user):
    """Test get_all_configured_exchanges with single exchange config."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert "binance" in result
    assert result["binance"] == {"encrypted_data": "binance_key"}
    assert len(result) == 1


def test_get_all_configured_exchanges_empty_valid_config(mock_user):
    """Test get_all_configured_exchanges returns empty dict for invalid inner configs."""
    mock_user.encrypted_api_keys = {
        "binance": {"api_key": "no_encrypted_data"}  # Missing encrypted_data
    }

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert "binance" not in result  # Skipped because no encrypted_data
    assert len(result) == 0


def test_get_all_configured_exchanges_string_value(mock_user):
    """Test get_all_configured_exchanges normalizes string values."""
    mock_user.encrypted_api_keys = {
        "binance": "just_a_string"
    }

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert "binance" in result
    assert result["binance"] == {"encrypted_data": "just_a_string"}


def test_get_all_configured_exchanges_skips_invalid(mock_user):
    """Test get_all_configured_exchanges skips invalid entries."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "valid_key"},
        "bybit": {"api_key": "invalid"}  # Missing encrypted_data
    }

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert "binance" in result
    assert "bybit" not in result  # Skipped because no encrypted_data


def test_get_all_configured_exchanges_normalizes_case(mock_user):
    """Test get_all_configured_exchanges normalizes exchange names to lowercase."""
    mock_user.encrypted_api_keys = {
        "BINANCE": {"encrypted_data": "binance_key"},
        "ByBit": {"encrypted_data": "bybit_key"}
    }

    result = ExchangeConfigService.get_all_configured_exchanges(mock_user)

    assert "binance" in result
    assert "bybit" in result


# --- Tests for has_valid_config ---

def test_has_valid_config_specific_exchange_true(mock_user):
    """Test has_valid_config returns True for valid specific exchange."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    result = ExchangeConfigService.has_valid_config(mock_user, "binance")

    assert result is True


def test_has_valid_config_specific_exchange_false(mock_user):
    """Test has_valid_config returns False for missing exchange."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    result = ExchangeConfigService.has_valid_config(mock_user, "bybit")

    assert result is False


def test_has_valid_config_any_exchange_true(mock_user):
    """Test has_valid_config returns True when any exchange exists."""
    mock_user.encrypted_api_keys = {
        "binance": {"encrypted_data": "binance_key"}
    }

    result = ExchangeConfigService.has_valid_config(mock_user)

    assert result is True


def test_has_valid_config_any_exchange_false(mock_user):
    """Test has_valid_config returns False when no exchanges exist."""
    mock_user.encrypted_api_keys = None

    result = ExchangeConfigService.has_valid_config(mock_user)

    assert result is False


def test_has_valid_config_empty_dict(mock_user):
    """Test has_valid_config returns False for empty dict."""
    mock_user.encrypted_api_keys = {}

    result = ExchangeConfigService.has_valid_config(mock_user)

    assert result is False


def test_has_valid_config_catches_exception(mock_user):
    """Test has_valid_config catches ExchangeConfigError."""
    mock_user.encrypted_api_keys = {
        "binance": {"api_key": "invalid"}  # Missing encrypted_data
    }

    result = ExchangeConfigService.has_valid_config(mock_user, "binance")

    assert result is False
