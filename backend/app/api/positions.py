from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.db.database import get_db_session
from app.schemas.position_group import PositionGroupSchema
from app.repositories.position_group import PositionGroupRepository

router = APIRouter()

@router.get("/{user_id}", response_model=List[PositionGroupSchema])
async def get_all_positions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieves all active position groups for a given user.
    """
    repo = PositionGroupRepository(db)
    positions = await repo.get_all_active_by_user(user_id)
    return [PositionGroupSchema.from_orm(pos) for pos in positions]

@router.get("/{user_id}/{group_id}", response_model=PositionGroupSchema)
async def get_position_group(
    user_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieves a specific position group for a given user.
    """
    repo = PositionGroupRepository(db)
    position = await repo.get_by_user_and_id(user_id, group_id)
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")
    return PositionGroupSchema.from_orm(position)