import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.db.types import GUID

from .base import Base


class RiskActionType(str, Enum):
    OFFSET_LOSS = "offset_loss"
    MANUAL_BLOCK = "manual_block"
    MANUAL_SKIP = "manual_skip"
    MANUAL_CLOSE = "manual_close"
    ENGINE_CLOSE = "engine_close"
    TP_HIT = "tp_hit"


class RiskAction(Base):
    """
    Records actions taken by the Risk Engine.
    """

    __tablename__ = "risk_actions"

    # Performance indexes for common queries
    __table_args__ = (
        Index('ix_risk_actions_action_type', 'action_type'),
        Index('ix_risk_actions_group_timestamp', 'group_id', 'timestamp'),
    )

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    group_id = Column(GUID, ForeignKey("position_groups.id"), nullable=False)

    action_type = Column(SQLAlchemyEnum(RiskActionType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Details for offset_loss
    loser_group_id = Column(GUID, ForeignKey("position_groups.id"))
    loser_pnl_usd = Column(Numeric(20, 10))

    # Details for winners (JSON array of {group_id, pnl_usd, quantity_closed})
    winner_details = Column(JSON)

    # Details for close actions (manual_close, engine_close, tp_hit)
    exit_price = Column(Numeric(20, 10))
    entry_price = Column(Numeric(20, 10))
    pnl_percent = Column(Numeric(10, 4))
    realized_pnl_usd = Column(Numeric(20, 10))
    quantity_closed = Column(Numeric(20, 10))
    duration_seconds = Column(Numeric(20, 2))  # Position duration in seconds

    notes = Column(String)

    group = relationship(
        "PositionGroup", foreign_keys=[group_id], back_populates="risk_actions", lazy="noload"
    )
    loser_group = relationship("PositionGroup", foreign_keys=[loser_group_id], lazy="noload")
