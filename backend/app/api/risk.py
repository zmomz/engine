from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.database import get_db_session
from app.schemas.position_group import PositionGroupSchema
from app.services.risk_engine import RiskEngineService
from app.repositories.position_group import PositionGroupRepository
from app.repositories.risk_action import RiskActionRepository
from app.repositories.dca_order import DCAOrderRepository
from app.services.exchange_abstraction.factory import get_exchange_connector
from app.services.order_management import OrderService
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig
from app.services.exchange_abstraction.interface import ExchangeInterface

router = APIRouter()

def get_risk_engine_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session)
) -> RiskEngineService:
    risk_engine_config: RiskEngineConfig = request.app.state.risk_engine_config
    dca_grid_config: DCAGridConfig = request.app.state.dca_grid_config
    exchange_connector: ExchangeInterface = request.app.state.exchange_connector

    async def session_factory():
        yield session

    return RiskEngineService(
        session_factory=session_factory,
        position_group_repository_class=PositionGroupRepository,
        risk_action_repository_class=RiskActionRepository,
        dca_order_repository_class=DCAOrderRepository,
        exchange_connector=exchange_connector,
        order_service_class=OrderService,
        risk_engine_config=risk_engine_config
    )

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