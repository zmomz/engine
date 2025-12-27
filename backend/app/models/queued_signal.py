from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
)

from app.db.types import GUID

from .base import Base


import uuid
from enum import Enum
from datetime import datetime


class QueueStatus(str, Enum):
    QUEUED = "queued"
    PROMOTED = "promoted"
    CANCELLED = "cancelled"


class QueuedSignal(Base):
    """
    Represents a signal waiting in the queue.
    """

    __tablename__ = "queued_signals"

    # Performance indexes for common queries
    __table_args__ = (
        Index('ix_queued_signals_user_status', 'user_id', 'status'),
        Index('ix_queued_signals_priority_score', 'priority_score'),
    )

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(Integer, nullable=False)
    side = Column(SQLAlchemyEnum("long", "short", name="signal_side_enum"), nullable=False)
    entry_price = Column(Numeric(20, 10), nullable=False)
    signal_payload = Column(JSON, nullable=False)

    queued_at = Column(DateTime, default=datetime.utcnow)
    replacement_count = Column(Integer, default=0)
    priority_score = Column(Numeric(20, 4), default=0.0)
    priority_explanation = Column(String, nullable=True)

    is_pyramid_continuation = Column(Boolean, default=False)
    current_loss_percent = Column(Numeric(20, 4))

    status = Column(
        SQLAlchemyEnum(QueueStatus, name="queue_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=QueueStatus.QUEUED.value,
    )
    promoted_at = Column(DateTime)
