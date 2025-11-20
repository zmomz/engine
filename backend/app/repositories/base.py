from typing import Generic, Type, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, pk: UUID) -> ModelType | None:
        return await self.session.get(self.model, pk)

    async def create(self, instance: ModelType) -> ModelType:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, pk: UUID) -> bool:
        instance = await self.get(pk)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False

    async def update(self, instance: ModelType) -> ModelType:
        self.session.add(instance)  # Re-add the instance to the session to track changes
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def count_by_status(self, statuses: list, for_update: bool = False) -> int:
        query = select(func.count(self.model.id)).where(self.model.status.in_(statuses))
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_by_status(self, statuses: list, for_update: bool = False) -> list[ModelType]:
        query = select(self.model).where(self.model.status.in_(statuses))
        if for_update:
            query = query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all(self, for_update: bool = False) -> list[ModelType]:
        query = select(self.model)
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().all()
