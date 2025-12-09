
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.dca_configuration import DCAConfiguration

class DCAConfigurationRepository:
    def __init__(self, session: Session):
        self.session = session

    async def get_by_id(self, config_id: UUID) -> Optional[DCAConfiguration]:
        result = await self.session.execute(select(DCAConfiguration).where(DCAConfiguration.id == config_id))
        return result.scalars().first()

    async def get_all_by_user(self, user_id: UUID) -> List[DCAConfiguration]:
        result = await self.session.execute(select(DCAConfiguration).where(DCAConfiguration.user_id == user_id))
        return result.scalars().all()

    async def get_specific_config(self, user_id: UUID, pair: str, timeframe: str, exchange: str) -> Optional[DCAConfiguration]:
        stmt = select(DCAConfiguration).where(
            and_(
                DCAConfiguration.user_id == user_id,
                DCAConfiguration.pair == pair,
                DCAConfiguration.timeframe == timeframe,
                DCAConfiguration.exchange == exchange
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, config: DCAConfiguration) -> DCAConfiguration:
        self.session.add(config)
        return config

    async def delete(self, config: DCAConfiguration) -> None:
        await self.session.delete(config)
