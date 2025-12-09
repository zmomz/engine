import uuid
from datetime import datetime
from decimal import Decimal

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
from sqlalchemy.orm import relationship

from app.db.types import GUID

from .base import Base


from enum import Enum


class PositionGroupStatus(str, Enum):
    WAITING = "waiting"
    LIVE = "live"
    PARTIALLY_FILLED = "partially_filled"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class PositionGroup(Base):
    """
    Represents a unique trading position defined by pair + timeframe.
    Contains multiple pyramids and DCA legs.
    """

    __tablename__ = "position_groups"

    # Identity
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    exchange = Column(String, nullable=False)  # "binance", "bybit", etc.
    symbol = Column(String, nullable=False)  # "BTCUSDT"
    timeframe = Column(Integer, nullable=False)  # in minutes (e.g., 15, 60, 240)
    side = Column(SQLAlchemyEnum("long", "short", name="position_side_enum"), nullable=False)

    # Status tracking
    status = Column(
        SQLAlchemyEnum(PositionGroupStatus, name="group_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PositionGroupStatus.WAITING.value,
    )

    # Pyramid tracking
    pyramid_count = Column(Integer, default=0)
    max_pyramids = Column(Integer, default=5)
    replacement_count = Column(Integer, default=0)

    # DCA tracking
    total_dca_legs = Column(Integer, nullable=False)
    filled_dca_legs = Column(Integer, default=0)

    # Financial metrics
    base_entry_price = Column(Numeric(20, 10), nullable=False)
    weighted_avg_entry = Column(Numeric(20, 10), nullable=False)
    total_invested_usd = Column(Numeric(20, 10), default=Decimal("0"))
    total_filled_quantity = Column(Numeric(20, 10), default=Decimal("0"))
    unrealized_pnl_usd = Column(Numeric(20, 10), default=Decimal("0"))
    unrealized_pnl_percent = Column(Numeric(10, 4), default=Decimal("0"))
    realized_pnl_usd = Column(Numeric(20, 10), default=Decimal("0"))

    # Take-profit configuration
    # Take-profit configuration
    tp_mode = Column(
        SQLAlchemyEnum("per_leg", "pyramid", "aggregate", "hybrid", name="tp_mode_enum"),
        nullable=False,
    )
    tp_aggregate_percent = Column(Numeric(10, 4))
    tp_pyramid_percent = Column(Numeric(10, 4)) # Unified TP % for pyramid mode

    # Risk engine tracking
    risk_timer_start = Column(DateTime)
    risk_timer_expires = Column(DateTime)
    risk_eligible = Column(Boolean, default=False)
    risk_blocked = Column(Boolean, default=False)
    risk_skip_once = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime)

    # Relationships
    pyramids = relationship(
        "Pyramid", back_populates="group", cascade="all, delete-orphan", lazy="noload"
    )
    dca_orders = relationship(
        "DCAOrder", back_populates="group", cascade="all, delete-orphan", lazy="noload"
    )
    risk_actions = relationship(
        "RiskAction", back_populates="group", cascade="all, delete-orphan", foreign_keys="[RiskAction.group_id]", lazy="noload"
    )
