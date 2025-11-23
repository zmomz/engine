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
    
    encrypted_keys = None
    # Handle API Key Encryption if provided
    if user_update.api_key and user_update.secret_key:
        encryption_service = EncryptionService()
        # encrypt_keys returns a dict that matches what we want to store
        encrypted_keys = encryption_service.encrypt_keys(user_update.api_key, user_update.secret_key)

    # Prepare update data
    update_data = user_update.dict(exclude_unset=True)
    
    # Remove raw keys from update data as they are not DB columns
    update_data.pop("api_key", None)
    update_data.pop("secret_key", None)
    
    # Explicitly set encrypted keys if they were generated
    if encrypted_keys:
        update_data["encrypted_api_keys"] = encrypted_keys

    # Apply updates to the current_user instance
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # Use the repository to save the updated instance
    updated_user = await user_repo.update(current_user)
    await db.commit()
    return updated_user
