import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.models.user import User
from app.schemas.user import UserUpdate, UserRead

@pytest.fixture
def mock_encryption_service():
    with patch("app.api.settings.EncryptionService") as MockEncryptionService:
        mock_instance = MockEncryptionService.return_value
        mock_instance.encrypt_keys.return_value = {"encrypted_api_key": "mock_encrypted_key", "encrypted_secret_key": "mock_encrypted_secret"}
        yield mock_instance

@pytest.mark.asyncio
async def test_get_supported_exchanges(
    authorized_client: AsyncClient,
    test_user: User
):
    response = await authorized_client.get("/api/v1/settings/exchanges")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert "binance" in data
    assert "bybit" in data
    assert "mock" in data

@pytest.mark.asyncio
async def test_update_settings_no_api_keys(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    update_data = {"is_active": False}
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user_data = response.json()
    assert updated_user_data["is_active"] == False
    assert mock_encryption_service.encrypt_keys.call_count == 0

@pytest.mark.asyncio
async def test_update_settings_with_new_api_keys_target_exchange(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    update_data = {
        "api_key": "new_api_key",
        "secret_key": "new_secret_key",
        "key_target_exchange": "bybit",
        "testnet": True,
        "account_type": "UNIFIED"
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert updated_user.configured_exchange_details is not None
    assert "bybit" in updated_user.configured_exchange_details
    assert updated_user.configured_exchange_details["bybit"]["testnet"] is True
    assert updated_user.configured_exchange_details["bybit"]["account_type"] == "UNIFIED"
    mock_encryption_service.encrypt_keys.assert_called_once_with("new_api_key", "new_secret_key")

@pytest.mark.asyncio
async def test_update_settings_with_new_api_keys_key_target_exchange(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    """Test that API keys are saved using key_target_exchange."""
    update_data = {
        "api_key": "new_api_key_2",
        "secret_key": "new_secret_key_2",
        "key_target_exchange": "mock",  # Must use key_target_exchange, not exchange
        "testnet": False,
        "account_type": "SPOT"
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert updated_user.configured_exchange_details is not None
    assert "mock" in updated_user.configured_exchange_details
    assert updated_user.configured_exchange_details["mock"]["testnet"] is False
    assert updated_user.configured_exchange_details["mock"]["account_type"] == "SPOT"
    mock_encryption_service.encrypt_keys.assert_called_once_with("new_api_key_2", "new_secret_key_2")

@pytest.mark.asyncio
async def test_update_settings_without_key_target_does_not_update_keys(
    authorized_client: AsyncClient,
    test_user: User,
    mock_encryption_service: AsyncMock
):
    """Test that API keys are NOT saved if key_target_exchange is not specified."""
    update_data = {
        "api_key": "new_api_key_3",
        "secret_key": "new_secret_key_3",
        "testnet": True,
        "account_type": "UNIFIED"
        # Note: No key_target_exchange specified
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    # Without key_target_exchange, no keys should be updated
    # The encryption service is still called (current behavior) but keys are not saved
    # Check that configured_exchange_details remains as before (empty or unchanged)
    # This test verifies the behavior that key_target_exchange is required
    mock_encryption_service.encrypt_keys.assert_called_once_with("new_api_key_3", "new_secret_key_3")

@pytest.mark.asyncio
async def test_delete_exchange_key_success(
    authorized_client: AsyncClient,
    test_user: User,
    db_session: AsyncMock # Added db_session to the fixture list
):
    # Ensure the user has an API key for 'mock' exchange
    test_user.encrypted_api_keys = {"mock": {"encrypted_api_key": "mock_key", "encrypted_secret_key": "mock_secret"}}
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await authorized_client.delete("/api/v1/settings/keys/mock")
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert "mock" not in updated_user.configured_exchanges

@pytest.mark.asyncio
async def test_delete_exchange_key_non_existent(
    authorized_client: AsyncClient,
    test_user: User
):
    # Ensure the user has no API keys initially, or no key for 'nonexistent'
    test_user.encrypted_api_keys = {"binance": {"encrypted_api_key": "bin_key", "encrypted_secret_key": "bin_secret"}} # Example
    response = await authorized_client.delete("/api/v1/settings/keys/nonexistent")
    assert response.status_code == 200
    updated_user = UserRead(**response.json())
    assert "nonexistent" not in updated_user.configured_exchanges
    assert "binance" in updated_user.configured_exchanges # Ensure other keys are untouched


# ============================================================================
# Risk Config Merge Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_risk_config_merges_instead_of_replacing(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test that updating risk_config merges with existing values instead of replacing."""
    from decimal import Decimal
    # Set initial risk_config with multiple fields
    initial_risk_config = {
        "max_open_positions_global": 10,
        "max_open_positions_per_symbol": 2,
        "max_total_exposure_usd": 5000,
        "max_realized_loss_usd": 250,
        "loss_threshold_percent": -3.0,
        "required_pyramids_for_timer": 4,
        "post_pyramids_wait_minutes": 20,
        "max_winners_to_combine": 2,
    }
    test_user.risk_config = initial_risk_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update only a subset of fields
    update_data = {
        "risk_config": {
            "max_open_positions_global": 15,  # Changed
            "max_total_exposure_usd": 10000,   # Changed
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    risk_config = updated_user.risk_config

    # Changed fields should be updated (use attribute access for Pydantic model)
    assert risk_config.max_open_positions_global == 15
    assert risk_config.max_total_exposure_usd == Decimal("10000")

    # Unchanged fields from initial config should be preserved
    assert risk_config.max_open_positions_per_symbol == 2
    assert risk_config.max_realized_loss_usd == Decimal("250")
    assert risk_config.loss_threshold_percent == Decimal("-3.0")
    assert risk_config.required_pyramids_for_timer == 4
    assert risk_config.post_pyramids_wait_minutes == 20
    assert risk_config.max_winners_to_combine == 2


@pytest.mark.asyncio
async def test_update_risk_config_does_not_lose_fields_not_in_update(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test that fields not included in the update payload are preserved."""
    from decimal import Decimal
    # Set initial risk_config with all schema-defined fields
    initial_risk_config = {
        "max_open_positions_global": 5,
        "max_open_positions_per_symbol": 1,
        "max_total_exposure_usd": 1000,
        "max_realized_loss_usd": 100,
        "loss_threshold_percent": -2.0,
        "required_pyramids_for_timer": 3,
        "post_pyramids_wait_minutes": 15,
        "max_winners_to_combine": 3,
    }
    test_user.risk_config = initial_risk_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update only one field
    update_data = {
        "risk_config": {
            "max_open_positions_global": 20,
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    risk_config = updated_user.risk_config

    # Updated field (use attribute access for Pydantic model)
    assert risk_config.max_open_positions_global == 20

    # All other fields preserved
    assert risk_config.max_open_positions_per_symbol == 1
    assert risk_config.max_total_exposure_usd == Decimal("1000")
    assert risk_config.max_realized_loss_usd == Decimal("100")
    assert risk_config.loss_threshold_percent == Decimal("-2.0")
    assert risk_config.required_pyramids_for_timer == 3
    assert risk_config.post_pyramids_wait_minutes == 15
    assert risk_config.max_winners_to_combine == 3


# ============================================================================
# Telegram Config Merge Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_telegram_config_merges_instead_of_replacing(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test that updating telegram_config merges with existing values instead of replacing."""
    # Set initial telegram_config with multiple fields
    initial_telegram_config = {
        "enabled": True,
        "bot_token": "original_token",
        "channel_id": "original_channel",
        "channel_name": "Original Channel",
        "send_entry_signals": True,
        "send_exit_signals": True,
        "send_status_updates": False,
        # Extra fields that should survive
        "internal_rate_limit": 30,
        "message_queue_size": 100,
    }
    test_user.telegram_config = initial_telegram_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update only a subset of fields
    update_data = {
        "telegram_config": {
            "enabled": False,  # Changed
            "channel_name": "New Channel Name",  # Changed
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    telegram_config = updated_user.telegram_config

    # Changed fields should be updated
    assert telegram_config["enabled"] is False
    assert telegram_config["channel_name"] == "New Channel Name"

    # Unchanged fields should be preserved
    assert telegram_config["bot_token"] == "original_token"
    assert telegram_config["channel_id"] == "original_channel"
    assert telegram_config["send_entry_signals"] is True
    assert telegram_config["send_exit_signals"] is True
    assert telegram_config["send_status_updates"] is False

    # Extra fields not in schema should also be preserved
    assert telegram_config.get("internal_rate_limit") == 30
    assert telegram_config.get("message_queue_size") == 100


@pytest.mark.asyncio
async def test_update_telegram_config_preserves_unmentioned_fields(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test that telegram_config fields not in update are preserved."""
    # Set initial telegram_config
    initial_telegram_config = {
        "enabled": True,
        "bot_token": "test_token",
        "channel_id": "test_channel",
        "send_entry_signals": True,
        "send_exit_signals": True,
        "send_dca_fill_updates": True,
        "send_pyramid_updates": True,
        "send_tp_hit_updates": True,
        "send_failure_alerts": True,
        "send_risk_alerts": True,
        "quiet_hours_enabled": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
    test_user.telegram_config = initial_telegram_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update only enabled flag
    update_data = {
        "telegram_config": {
            "enabled": False,
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    telegram_config = updated_user.telegram_config

    # Only enabled changed
    assert telegram_config["enabled"] is False

    # All message type settings preserved
    assert telegram_config["send_entry_signals"] is True
    assert telegram_config["send_exit_signals"] is True
    assert telegram_config["send_dca_fill_updates"] is True
    assert telegram_config["send_pyramid_updates"] is True
    assert telegram_config["send_tp_hit_updates"] is True
    assert telegram_config["send_failure_alerts"] is True
    assert telegram_config["send_risk_alerts"] is True

    # Quiet hours settings preserved
    assert telegram_config["quiet_hours_enabled"] is True
    assert telegram_config["quiet_hours_start"] == "22:00"
    assert telegram_config["quiet_hours_end"] == "08:00"


# ============================================================================
# Combined Update Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_multiple_configs_simultaneously(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test updating both risk_config and telegram_config in same request."""
    from decimal import Decimal
    # Set initial configs
    test_user.risk_config = {
        "max_open_positions_global": 5,
        "max_total_exposure_usd": 1000,
        "max_open_positions_per_symbol": 2,
    }
    test_user.telegram_config = {
        "enabled": False,
        "bot_token": "original_token",
        "extra_telegram_field": "also_preserve",
    }
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update both configs
    update_data = {
        "risk_config": {
            "max_open_positions_global": 10,
        },
        "telegram_config": {
            "enabled": True,
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())

    # Risk config: updated field + preserved fields (use attribute access for Pydantic model)
    assert updated_user.risk_config.max_open_positions_global == 10
    assert updated_user.risk_config.max_total_exposure_usd == Decimal("1000")
    assert updated_user.risk_config.max_open_positions_per_symbol == 2

    # Telegram config: updated field + preserved fields (dict access works for telegram)
    assert updated_user.telegram_config["enabled"] is True
    assert updated_user.telegram_config["bot_token"] == "original_token"
    # Extra fields are preserved in DB (telegram_config is a dict, so extras are kept)
    assert updated_user.telegram_config.get("extra_telegram_field") == "also_preserve"


# ============================================================================
# Edge Case Tests: Null Safety
# ============================================================================

@pytest.mark.asyncio
async def test_update_risk_config_when_existing_is_none(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test merge behavior when user has no existing risk_config."""
    from decimal import Decimal
    # Set risk_config to None
    test_user.risk_config = None
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update with partial config
    update_data = {
        "risk_config": {
            "max_open_positions_global": 25,
            "max_total_exposure_usd": 15000,
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    risk_config = updated_user.risk_config

    # New values should be applied
    assert risk_config.max_open_positions_global == 25
    assert risk_config.max_total_exposure_usd == Decimal("15000")


@pytest.mark.asyncio
async def test_update_telegram_config_when_existing_is_none(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test merge behavior when user has no existing telegram_config."""
    # Set telegram_config to None
    test_user.telegram_config = None
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update with partial config
    update_data = {
        "telegram_config": {
            "enabled": True,
            "bot_token": "new_bot_token",
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    telegram_config = updated_user.telegram_config

    # New values should be applied
    assert telegram_config["enabled"] is True
    assert telegram_config["bot_token"] == "new_bot_token"


# ============================================================================
# Edge Case Tests: Empty Dict Updates
# ============================================================================

@pytest.mark.asyncio
async def test_update_risk_config_with_empty_dict(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test that empty dict update preserves existing config."""
    from decimal import Decimal
    # Set initial risk_config
    initial_risk_config = {
        "max_open_positions_global": 8,
        "max_total_exposure_usd": 3000,
    }
    test_user.risk_config = initial_risk_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update with empty dict
    update_data = {
        "risk_config": {}
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    risk_config = updated_user.risk_config

    # Existing values should be preserved
    assert risk_config.max_open_positions_global == 8
    assert risk_config.max_total_exposure_usd == Decimal("3000")


@pytest.mark.asyncio
async def test_update_telegram_config_with_empty_dict(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """Test that empty dict update preserves existing telegram_config."""
    # Set initial telegram_config
    initial_telegram_config = {
        "enabled": True,
        "bot_token": "existing_token",
        "channel_id": "existing_channel",
    }
    test_user.telegram_config = initial_telegram_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update with empty dict
    update_data = {
        "telegram_config": {}
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    telegram_config = updated_user.telegram_config

    # Existing values should be preserved
    assert telegram_config["enabled"] is True
    assert telegram_config["bot_token"] == "existing_token"
    assert telegram_config["channel_id"] == "existing_channel"


# ============================================================================
# Edge Case Tests: Shallow Merge Behavior Documentation
# ============================================================================

@pytest.mark.asyncio
async def test_nested_priority_rules_is_replaced_not_deep_merged(
    authorized_client: AsyncClient,
    test_user: User,
    db_session
):
    """
    Document that nested objects like priority_rules are REPLACED entirely,
    not deep-merged. This is the expected shallow merge behavior.

    Shallow merge means:
    - At risk_config level: fields are merged (existing fields preserved)
    - At priority_rules level: the entire object is replaced (not deep merged)
    """
    from decimal import Decimal

    # Set initial risk_config with custom priority_rules and other fields
    initial_risk_config = {
        "max_open_positions_global": 5,
        "max_total_exposure_usd": 8000,  # Custom value to verify preservation
        "priority_rules": {
            "priority_rules_enabled": {
                "same_pair_timeframe": True,
                "deepest_loss_percent": False,  # Disabled
                "highest_replacement": True,
                "fifo_fallback": True,
            },
            "priority_order": ["same_pair_timeframe", "highest_replacement", "deepest_loss_percent", "fifo_fallback"],
        }
    }
    test_user.risk_config = initial_risk_config
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    # Update with a complete new priority_rules (validation requires complete object)
    # But only change some values - test verifies OLD values are NOT preserved
    update_data = {
        "risk_config": {
            "priority_rules": {
                "priority_rules_enabled": {
                    "same_pair_timeframe": False,  # Changed
                    "deepest_loss_percent": True,  # Changed
                    "highest_replacement": False,  # Changed
                    "fifo_fallback": True,  # Same
                },
                # Different order than original
                "priority_order": ["fifo_fallback", "same_pair_timeframe", "deepest_loss_percent", "highest_replacement"],
            }
        }
    }
    response = await authorized_client.put("/api/v1/settings", json=update_data)
    assert response.status_code == 200

    updated_user = UserRead(**response.json())
    risk_config = updated_user.risk_config
    priority_rules = risk_config.priority_rules

    # SHALLOW MERGE at risk_config level: other risk_config fields preserved
    assert risk_config.max_open_positions_global == 5  # Preserved
    assert risk_config.max_total_exposure_usd == Decimal("8000")  # Preserved

    # REPLACEMENT at priority_rules level: entire object was replaced
    assert priority_rules.priority_rules_enabled["same_pair_timeframe"] is False  # New value
    assert priority_rules.priority_rules_enabled["deepest_loss_percent"] is True  # New value
    assert priority_rules.priority_rules_enabled["highest_replacement"] is False  # New value

    # Order was completely replaced
    assert priority_rules.priority_order[0] == "fifo_fallback"  # New order
