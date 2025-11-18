import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.db.types import GUID

from .base import Base


from enum import Enum


class PyramidStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"


class Pyramid(Base):
    """
    Represents a single pyramid entry within a PositionGroup.
    """

    __tablename__ = "pyramids"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    group_id = Column(GUID, ForeignKey("position_groups.id"), nullable=False)
    pyramid_index = Column(Integer, nullable=False)  # 0-4

    entry_price = Column(Numeric(20, 10), nullable=False)
    entry_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    signal_id = Column(String)  # TradingView signal ID

    status = Column(
        SQLAlchemyEnum(PyramidStatus, name="pyramid_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PyramidStatus.PENDING,
    )
    dca_config = Column(JSON, nullable=False)

    group = relationship("PositionGroup", back_populates="pyramids", lazy="noload")
    dca_orders = relationship(
        "DCAOrder", back_populates="pyramid", cascade="all, delete-orphan", lazy="noload"
    )
