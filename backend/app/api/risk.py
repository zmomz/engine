from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import os

from app.db.database import get_db_session
from app.schemas.position_group import PositionGroupSchema
from app.services.risk_engine import RiskEngineService
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.order_management import OrderService
from app.schemas.grid_config import RiskEngineConfig
from app.services.exchange_abstraction.interface import ExchangeInterface
from app.models.user import User
from app.api.dependencies.users import get_current_active_user
from app.core.security import EncryptionService

router = APIRouter()

def create_risk_engine_service(session: AsyncSession, user: User) -> RiskEngineService:
    # Load encryption service
    try:
        encryption_service = EncryptionService()
    except ValueError:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Encryption service configuration error.")

    # Decrypt keys
    if not user.encrypted_api_keys:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exchange API keys are missing.")
    
    try:
        api_key, secret_key = encryption_service.decrypt_keys(user.encrypted_api_keys)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to decrypt API keys: {str(e)}")

    try:
        exchange_connector: ExchangeInterface = get_exchange_connector(user.exchange, api_key, secret_key)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to connect to exchange: {str(e)}")

    try:
        risk_engine_config = RiskEngineConfig.model_validate(user.risk_config)
    except:
        risk_engine_config = RiskEngineConfig()

    async def session_factory():
        yield session

    return RiskEngineService(
        session_factory=session_factory,
        position_group_repository_class=PositionGroupRepository,
        risk_action_repository_class=RiskActionRepository,
        dca_order_repository_class=DCAOrderRepository,
        exchange_connector=exchange_connector,
        order_service_class=OrderService,
        risk_engine_config=risk_engine_config,
        user=user
    )

def get_risk_engine_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user)
) -> RiskEngineService:
    return create_risk_engine_service(session, user)

@router.get("/status")
async def get_risk_engine_status(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user)
):
    """
    Retrieves the current status of the Risk Engine, including potential actions.
    Handles cases where the engine is not fully configured.
    """
    if not user.encrypted_api_keys:
        return {
            "status": "not_configured",
            "message": "Exchange API keys are missing. Please configure them in Settings.",
            "active_positions": 0,
            "risk_level": "unknown"
        }

    try:
        risk_engine_service = create_risk_engine_service(session, user)
        status_data = await risk_engine_service.get_current_status()
        return status_data
    except HTTPException as e:
        # If creation fails (e.g. bad keys), return error status but don't crash frontend polling
        return {
            "status": "error",
            "message": e.detail,
            "active_positions": 0,
            "risk_level": "unknown"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "active_positions": 0,
            "risk_level": "unknown"
        }

@router.post("/run-evaluation")
async def run_risk_evaluation(
    risk_engine_service: RiskEngineService = Depends(get_risk_engine_service)
):
    """
    Triggers an immediate risk evaluation run.
    """
    try:
        result = await risk_engine_service.run_single_evaluation()
        return {"message": "Risk evaluation initiated.", "result": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{group_id}/block", response_model=PositionGroupSchema)
async def block_risk_for_group(
    group_id: uuid.UUID,
    risk_engine_service: RiskEngineService = Depends(get_risk_engine_service)
):
    """
    Manually block a position from being considered by the Risk Engine.
    """
    try:
        updated_group = await risk_engine_service.set_risk_blocked(group_id, True)
        return PositionGroupSchema.from_orm(updated_group)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{group_id}/unblock", response_model=PositionGroupSchema)
async def unblock_risk_for_group(
    group_id: uuid.UUID,
    risk_engine_service: RiskEngineService = Depends(get_risk_engine_service)
):
    """
    Manually unblock a position, allowing it to be considered by the Risk Engine again.
    """
    try:
        updated_group = await risk_engine_service.set_risk_blocked(group_id, False)
        return PositionGroupSchema.from_orm(updated_group)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{group_id}/skip", response_model=PositionGroupSchema)
async def skip_next_risk_evaluation(
    group_id: uuid.UUID,
    risk_engine_service: RiskEngineService = Depends(get_risk_engine_service)
):
    """
    Manually skip the next risk evaluation for a position.
    """
    try:
        updated_group = await risk_engine_service.set_risk_skip_once(group_id, True)
        return PositionGroupSchema.from_orm(updated_group)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))