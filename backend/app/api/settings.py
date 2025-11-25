from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.users import get_current_active_user
from app.db.database import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate, UserRead
from app.services.exchange_abstraction.factory import get_supported_exchanges
from app.core.security import EncryptionService

router = APIRouter()

@router.get("/exchanges", response_model=List[str])
async def get_exchanges(
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves the list of supported exchanges.
    """
    return get_supported_exchanges()

@router.get("", response_model=UserRead)
async def get_settings(
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieve the current user's settings.
    """
    return current_user

@router.put("", response_model=UserRead)
async def update_settings(
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
    if user_update.api_key and user_update.secret_key:
        encryption_service = EncryptionService()
        new_encrypted_keys = encryption_service.encrypt_keys(user_update.api_key, user_update.secret_key)
        
        # Get existing keys or initialize empty dict
        # CRITICAL: Create a copy to ensure SQLAlchemy detects the change to the JSON column
        current_keys = dict(current_user.encrypted_api_keys or {})
        
        # Determine which exchange these keys are for
        # Use the explicit target, or the exchange from the update, or fallback to the user's current active exchange
        target_exchange = user_update.key_target_exchange or user_update.exchange or current_user.exchange
        
        # Update the keys for this specific exchange
        current_keys[target_exchange] = new_encrypted_keys
        
        # Explicitly set the field on the user object with the NEW dictionary
        # This ensures SQLAlchemy sees the 'set' event on the JSON column
        update_data["encrypted_api_keys"] = current_keys
        
        # Also direct assignment to be double sure before repository update (though loop below handles it)
        current_user.encrypted_api_keys = current_keys

    # Remove raw keys and target from update data as they are not DB columns
    update_data.pop("api_key", None)
    update_data.pop("secret_key", None)
    update_data.pop("key_target_exchange", None)

    # Apply updates to the current_user instance
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Use the repository to save the updated instance
    updated_user = await user_repo.update(current_user)
    await db.commit()
    return updated_user

@router.delete("/keys/{exchange}", response_model=UserRead)
async def delete_exchange_key(
    exchange: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """
    Remove API keys for a specific exchange.
    """
    user_repo = UserRepository(db)
    
    current_keys = current_user.encrypted_api_keys
    if current_keys and exchange in current_keys:
        # Create a new dictionary to ensure SQLAlchemy detects the change
        new_keys = current_keys.copy()
        del new_keys[exchange]
        current_user.encrypted_api_keys = new_keys
        
        await user_repo.update(current_user)
        await db.commit()
    
    return current_user
