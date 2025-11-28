from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.db.database import get_db_session, AsyncSessionLocal
from app.schemas.position_group import PositionGroupSchema
from app.repositories.position_group import PositionGroupRepository
from app.services.order_management import OrderService # New import
from app.services.position_manager import PositionManagerService
from app.services.grid_calculator import GridCalculatorService
from app.api.dependencies.users import get_current_active_user # New import
from app.models.user import User # New import
from app.exceptions import APIError # New import
from app.core.security import EncryptionService
from app.services.exchange_abstraction.factory import get_exchange_connector

router = APIRouter()

async def get_order_service(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
) -> OrderService:
    # Use user's credentials to initialize the exchange connector
    if not current_user.encrypted_api_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have API keys configured."
        )

    encryption_service = EncryptionService()
    try:
        # Handle multi-exchange keys
        encrypted_data = current_user.encrypted_api_keys
        if isinstance(encrypted_data, dict):
             if current_user.exchange in encrypted_data:
                 encrypted_data = encrypted_data[current_user.exchange]
             elif "encrypted_data" not in encrypted_data:
                 raise ValueError(f"No API keys found for exchange {current_user.exchange}")

        api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
        exchange_connector = get_exchange_connector(
            exchange_type=current_user.exchange or "binance", # Default to binance if not set
            api_key=api_key,
            secret_key=secret_key
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize exchange connector: {str(e)}"
        )

    return OrderService(
        session=db,
        user=current_user,
        exchange_connector=exchange_connector
    )

@router.get("/{user_id}/history", response_model=List[PositionGroupSchema])
async def get_position_history(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves all historical (closed) position groups for a given user.
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's history.")
        
    repo = PositionGroupRepository(db)
    positions = await repo.get_closed_by_user(user_id)
    return [PositionGroupSchema.from_orm(pos) for pos in positions]

@router.get("/active", response_model=List[PositionGroupSchema])
async def get_current_user_active_positions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieves all active position groups for the current authenticated user.
    """
    repo = PositionGroupRepository(db)
    # Use the more inclusive getter that matches dashboard logic (includes live, partially_filled, closing)
    positions = await repo.get_active_position_groups_for_user(current_user.id)
    return [PositionGroupSchema.from_orm(pos) for pos in positions]

@router.get("/{user_id}", response_model=List[PositionGroupSchema])
async def get_all_positions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves all active position groups for a given user.
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's positions.")

    repo = PositionGroupRepository(db)
    # Use the more inclusive getter that matches dashboard logic
    positions = await repo.get_active_position_groups_for_user(user_id)
    return [PositionGroupSchema.from_orm(pos) for pos in positions]

@router.get("/{user_id}/{group_id}", response_model=PositionGroupSchema)
async def get_position_group(
    user_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves a specific position group for a given user.
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this position group.")

    repo = PositionGroupRepository(db)
    position = await repo.get_by_user_and_id(user_id, group_id)
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")
    return PositionGroupSchema.from_orm(position)

@router.post("/{group_id}/close", response_model=PositionGroupSchema)
async def force_close_position(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Initiates the force-closing process for an active position group.
    """
    try:
        # 1. Fetch the position group to identify the exchange
        repo = PositionGroupRepository(db)
        position_group = await repo.get_by_user_and_id(current_user.id, group_id)
        if not position_group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position group not found.")

        # 2. Get credentials for the specific exchange
        target_exchange = position_group.exchange
        encryption_service = EncryptionService()
        
        api_key = None
        secret_key = None
        
        # Handle multi-exchange keys
        encrypted_data = current_user.encrypted_api_keys
        if isinstance(encrypted_data, dict):
             if target_exchange in encrypted_data:
                 encrypted_data = encrypted_data[target_exchange]
                 api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
             elif "encrypted_data" in encrypted_data and (current_user.exchange == target_exchange or not current_user.exchange):
                  # Legacy fallback
                 api_key, secret_key = encryption_service.decrypt_keys(encrypted_data)
        
        if not api_key:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No API keys configured for exchange: {target_exchange}"
            )

        # 3. Initialize OrderService dynamically
        exchange_connector = get_exchange_connector(
            exchange_type=target_exchange,
            api_key=api_key,
            secret_key=secret_key
        )
        
        order_service = OrderService(
            session=db,
            user=current_user,
            exchange_connector=exchange_connector
        )

        # 4. Mark as CLOSING
        updated_position = await order_service.execute_force_close(group_id)
        
        # Commit to release lock
        await db.commit()

        # 5. Execute the actual close logic
        position_manager = PositionManagerService(
            session_factory=AsyncSessionLocal,
            user=current_user,
            position_group_repository_class=PositionGroupRepository,
            grid_calculator_service=GridCalculatorService(),
            order_service_class=OrderService,
            exchange_connector=exchange_connector
        )

        await position_manager.handle_exit_signal(updated_position.id)
        
        # Refresh
        await db.refresh(updated_position)

        return PositionGroupSchema.from_orm(updated_position)
    except APIError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))