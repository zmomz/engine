from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List
import uuid

from app.schemas.queued_signal import QueuedSignalSchema
from app.services.queue_manager import QueueManagerService
from app.api.dependencies.users import get_current_active_user
from app.models.user import User

router = APIRouter()

def get_queue_manager_service(request: Request) -> QueueManagerService:
    return request.app.state.queue_manager_service

@router.get("/", response_model=List[QueuedSignalSchema])
async def get_all_queued_signals(
    queue_manager_service: QueueManagerService = Depends(get_queue_manager_service),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves all queued signals.
    """
    queued_signals = await queue_manager_service.get_all_queued_signals(user_id=current_user.id)
    return [QueuedSignalSchema.from_orm(signal) for signal in queued_signals]

@router.post("/{signal_id}/promote", response_model=QueuedSignalSchema)
async def promote_queued_signal(
    signal_id: uuid.UUID,
    queue_manager_service: QueueManagerService = Depends(get_queue_manager_service),
    current_user: User = Depends(get_current_active_user)
):
    """
    Promotes a queued signal to the active pool if a slot is available.
    """
    promoted_signal = await queue_manager_service.promote_specific_signal(signal_id, user_id=current_user.id)
    if not promoted_signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queued signal not found or could not be promoted.")
    return QueuedSignalSchema.from_orm(promoted_signal)

@router.delete("/{signal_id}", response_model=dict)
async def remove_queued_signal(
    signal_id: uuid.UUID,
    queue_manager_service: QueueManagerService = Depends(get_queue_manager_service),
    current_user: User = Depends(get_current_active_user)
):
    """
    Removes a queued signal.
    """
    success = await queue_manager_service.remove_from_queue(signal_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queued signal not found.")
    return {"message": "Queued signal removed successfully."}

@router.post("/{signal_id}/force-add", response_model=QueuedSignalSchema)
async def force_add_to_pool(
    signal_id: uuid.UUID,
    queue_manager_service: QueueManagerService = Depends(get_queue_manager_service),
    current_user: User = Depends(get_current_active_user)
):
    """
    Forces a queued signal to be added to the active pool, overriding position limits.
    """
    forced_signal = await queue_manager_service.force_add_specific_signal_to_pool(signal_id, user_id=current_user.id)
    if not forced_signal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queued signal not found or could not be forced into pool.")
    return QueuedSignalSchema.from_orm(forced_signal)
