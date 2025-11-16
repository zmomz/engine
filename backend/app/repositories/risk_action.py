from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RiskAction
from app.repositories.base import BaseRepository


class RiskActionRepository(BaseRepository[RiskAction]):
    def __init__(self, session: AsyncSession):
        super().__init__(RiskAction, session)
