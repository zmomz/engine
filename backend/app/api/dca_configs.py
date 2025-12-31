
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db_session as get_db
from app.api.dependencies.users import get_current_user
from app.models.user import User
from app.models.dca_configuration import DCAConfiguration
from app.repositories.dca_configuration import DCAConfigurationRepository
from app.schemas.grid_config import (
    DCAConfigurationSchema,
    DCAConfigurationCreate,
    DCAConfigurationUpdate
)

router = APIRouter()


def normalize_pair(pair: str) -> str:
    """Normalize pair format: BTCUSDT -> BTC/USDT"""
    if '/' in pair:
        return pair
    if len(pair) > 3:
        if pair.endswith('USDT'):
            return pair[:-4] + '/' + pair[-4:]
        elif pair.endswith(('USD', 'BTC', 'ETH', 'BNB')):
            return pair[:-3] + '/' + pair[-3:]
    return pair

@router.get("/", response_model=List[DCAConfigurationSchema])
async def get_my_dca_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all DCA configurations for the current user.
    """
    repo = DCAConfigurationRepository(db)
    # Using async method in sync route? If repo is async, we need async def.
    # Checking other files, it seems most are async.
    configs = await repo.get_all_by_user(current_user.id)
    return [config.to_dict() for config in configs] # Convert to dict compatible with Pydantic

@router.post("/", response_model=DCAConfigurationSchema)
async def create_dca_config(
    config_in: DCAConfigurationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new DCA configuration.
    """
    repo = DCAConfigurationRepository(db)

    # Normalize pair format (BTCUSDT -> BTC/USDT)
    normalized_pair = normalize_pair(config_in.pair)

    # Check if exists
    existing = await repo.get_specific_config(
        user_id=current_user.id,
        pair=normalized_pair,
        timeframe=config_in.timeframe,
        exchange=config_in.exchange
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Configuration already exists for {normalized_pair} {config_in.timeframe} on {config_in.exchange}"
        )

    new_config = DCAConfiguration(
        user_id=current_user.id,
        pair=normalized_pair,
        timeframe=config_in.timeframe,
        exchange=config_in.exchange,
        entry_order_type=config_in.entry_order_type,
        dca_levels=[level.model_dump(mode='json') for level in config_in.dca_levels],
        pyramid_specific_levels={
            k: [l.model_dump(mode='json') for l in v]
            for k, v in (config_in.pyramid_specific_levels or {}).items()
        },
        tp_mode=config_in.tp_mode,
        tp_settings=config_in.tp_settings,
        max_pyramids=config_in.max_pyramids,
        # Capital Override Settings
        use_custom_capital=config_in.use_custom_capital if config_in.use_custom_capital is not None else False,
        custom_capital_usd=float(config_in.custom_capital_usd) if config_in.custom_capital_usd is not None else 200.0,
        pyramid_custom_capitals={k: float(v) for k, v in (config_in.pyramid_custom_capitals or {}).items()}
    )
    
    created = await repo.create(new_config)
    await db.commit()
    await db.refresh(created)
    return created.to_dict()

@router.put("/{config_id}", response_model=DCAConfigurationSchema)
async def update_dca_config(
    config_id: str,
    config_update: DCAConfigurationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a DCA configuration.
    """
    repo = DCAConfigurationRepository(db)
    config = await repo.get_by_id(config_id)
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    if config.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if config_update.entry_order_type:
        config.entry_order_type = config_update.entry_order_type
    if config_update.dca_levels is not None:
        config.dca_levels = [level.model_dump(mode='json') for level in config_update.dca_levels]
    if config_update.pyramid_specific_levels is not None:
        config.pyramid_specific_levels = {
            k: [l.model_dump(mode='json') for l in v]
            for k, v in config_update.pyramid_specific_levels.items()
        }
    if config_update.tp_mode:
        config.tp_mode = config_update.tp_mode
    if config_update.tp_settings is not None:
        config.tp_settings = config_update.tp_settings
    if config_update.max_pyramids is not None:
        config.max_pyramids = config_update.max_pyramids
    # Capital Override Settings
    if config_update.use_custom_capital is not None:
        config.use_custom_capital = config_update.use_custom_capital
    if config_update.custom_capital_usd is not None:
        config.custom_capital_usd = float(config_update.custom_capital_usd)
    if config_update.pyramid_custom_capitals is not None:
        config.pyramid_custom_capitals = {k: float(v) for k, v in config_update.pyramid_custom_capitals.items()}

    await db.commit()
    await db.refresh(config)
    return config.to_dict()

@router.delete("/{config_id}")
async def delete_dca_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a DCA configuration.
    """
    repo = DCAConfigurationRepository(db)
    config = await repo.get_by_id(config_id)
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    if config.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    await repo.delete(config)
    await db.commit()
    return {"message": "Configuration deleted"}
