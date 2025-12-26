from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.users import get_current_active_user
from app.db.database import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate, UserRead
from app.services.exchange_abstraction.factory import get_supported_exchanges
from app.core.security import EncryptionService
from app.rate_limiter import limiter

router = APIRouter()

@router.get("/exchanges", response_model=List[str])
@limiter.limit("30/minute")
async def get_exchanges(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves the list of supported exchanges.
    """
    return get_supported_exchanges()

@router.get("", response_model=UserRead)
@limiter.limit("30/minute")
async def get_settings(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve the current user's settings.
    """
    return current_user

@router.put("", response_model=UserRead)
@limiter.limit("10/minute")
async def update_settings(
    request: Request,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update the current user's settings.
    """
    user_repo = UserRepository(db)
    
    # Prepare update data
    update_data = user_update.model_dump(mode='json', exclude_unset=True)
    
    # Handle API Key Encryption if provided
    # Handle API Key Encryption if provided
    if user_update.api_key and user_update.secret_key:
        encryption_service = EncryptionService()
        new_encrypted_keys_data = encryption_service.encrypt_keys(user_update.api_key, user_update.secret_key)

        # The `new_encrypted_keys_data` is already a dictionary like {"encrypted_data": "..."}
        exchange_config = new_encrypted_keys_data # Start with the encrypted data
        if user_update.testnet is not None:
            exchange_config["testnet"] = user_update.testnet
        if user_update.account_type:
            exchange_config["account_type"] = user_update.account_type

        current_keys = dict(current_user.encrypted_api_keys or {})
        raw_target = user_update.key_target_exchange or user_update.exchange or current_user.exchange
        target_exchange = raw_target.lower() if raw_target else None

        if target_exchange:
            # Update the config for this specific exchange
            current_keys[target_exchange] = exchange_config

            update_data["encrypted_api_keys"] = current_keys
            current_user.encrypted_api_keys = current_keys
    # Remove raw keys and target from update data as they are not DB columns
    update_data.pop("api_key", None)
    update_data.pop("secret_key", None)
    update_data.pop("key_target_exchange", None)
    update_data.pop("testnet", None) # Added to remove from update_data
    update_data.pop("account_type", None) # Added to remove from update_data
    
    # Normalize 'exchange' field if present in update
    if "exchange" in update_data and update_data["exchange"]:
        update_data["exchange"] = update_data["exchange"].lower()

    # Apply updates to the current_user instance
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Use the repository to save the updated instance
    updated_user = await user_repo.update(current_user)
    await db.commit()
    return updated_user

@router.delete("/keys/{exchange}", response_model=UserRead)
@limiter.limit("10/minute")
async def delete_exchange_key(
    request: Request,
    exchange: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Remove API keys for a specific exchange.
    """
    user_repo = UserRepository(db)
    
    target_exchange = exchange.lower()
    
    current_keys = current_user.encrypted_api_keys
    if current_keys and target_exchange in current_keys:
        # Create a new dictionary to ensure SQLAlchemy detects the change
        new_keys = current_keys.copy()
        del new_keys[target_exchange]
        current_user.encrypted_api_keys = new_keys
        
        await user_repo.update(current_user)
        await db.commit()
    
    return current_user
