from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pyramid
from app.repositories.base import BaseRepository


class PyramidRepository(BaseRepository[Pyramid]):
    def __init__(self, session: AsyncSession):
        super().__init__(Pyramid, session)
