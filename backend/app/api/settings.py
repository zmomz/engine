from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.signature_validation import SignatureValidator
from app.db.database import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate, UserRead

router = APIRouter()

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
