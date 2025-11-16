import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
)

from app.db.types import GUID

from .base import Base


from enum import Enum


class QueueStatus(str, Enum):
    QUEUED = "queued"
    PROMOTED = "promoted"
    CANCELLED = "cancelled"


class QueuedSignal(Base):
    """
    Represents a signal waiting in the queue.
    """

    __tablename__ = "queued_signals"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, nullable=False)  # ForeignKey("users.id")

    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(Integer, nullable=False)
    side = Column(SQLAlchemyEnum("long", "short", name="signal_side_enum"), nullable=False)
    entry_price = Column(Numeric(20, 10), nullable=False)
    signal_payload = Column(JSON, nullable=False)

    queued_at = Column(DateTime, default=datetime.utcnow)
    replacement_count = Column(Integer, default=0)
    priority_score = Column(Numeric(20, 4), default=0.0)

    is_pyramid_continuation = Column(Boolean, default=False)
    current_loss_percent = Column(Numeric(10, 4))

    status = Column(
        SQLAlchemyEnum("queued", "promoted", "cancelled", name="queue_status_enum"),
        nullable=False,
        default="queued",
    )
    promoted_at = Column(DateTime)
