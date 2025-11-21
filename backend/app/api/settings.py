from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.signature_validation import SignatureValidator
from app.api.dependencies.users import get_current_active_user
from app.db.database import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate, UserRead
from app.services.exchange_abstraction.factory import get_supported_exchanges

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
    current_user: User = Depends(SignatureValidator()),
):
    """
    Retrieve the current user's settings.
    """
    return current_user

@router.put("", response_model=UserRead)
async def update_settings(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(SignatureValidator()),
):
    """
    Update the current user's settings.
    """
    user_repo = UserRepository(db)
    updated_user = await user_repo.update(db_obj=current_user, obj_in=user_update)
    await db.commit()
    return updated_user
