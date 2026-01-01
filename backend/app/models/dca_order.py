import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.db.types import GUID

from .base import Base


class OrderStatus(str, Enum):
    PENDING = "pending"
    TRIGGER_PENDING = "trigger_pending" # New status for Market Entry Watch
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class DCAOrder(Base):
    """
    Represents a single DCA order (limit order at specific price level).
    """

    __tablename__ = "dca_orders"

    # Performance indexes for common queries
    __table_args__ = (
        Index('ix_dca_orders_group_status', 'group_id', 'status'),
        Index('ix_dca_orders_pyramid_id', 'pyramid_id'),
        Index('ix_dca_orders_exchange_order_id', 'exchange_order_id', postgresql_where="exchange_order_id IS NOT NULL"),
        Index('ix_dca_orders_tp_order_id', 'tp_order_id', postgresql_where="tp_order_id IS NOT NULL"),
    )

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    group_id = Column(GUID, ForeignKey("position_groups.id"), nullable=False)
    pyramid_id = Column(GUID, ForeignKey("pyramids.id"), nullable=False)

    exchange_order_id = Column(String)
    leg_index = Column(Integer, nullable=False)

    symbol = Column(String, nullable=False)
    side = Column(SQLAlchemyEnum("buy", "sell", name="order_side_enum"), nullable=False)
    order_type = Column(
        SQLAlchemyEnum(OrderType, name="order_type_enum", values_callable=lambda x: [e.value for e in x]), default=OrderType.LIMIT
    )
    price = Column(Numeric(20, 10), nullable=False)
    quantity = Column(Numeric(20, 10), nullable=False)

    gap_percent = Column(Numeric(10, 4), nullable=False)
    weight_percent = Column(Numeric(10, 4), nullable=False)
    tp_percent = Column(Numeric(10, 4), nullable=False)
    tp_price = Column(Numeric(20, 10), nullable=False)

    status = Column(
        SQLAlchemyEnum(OrderStatus, name="order_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=OrderStatus.PENDING.value,
    )
    filled_quantity = Column(Numeric(20, 10), default=Decimal("0"))
    avg_fill_price = Column(Numeric(20, 10))
    fee = Column(Numeric(20, 10), default=Decimal("0"))
    fee_currency = Column(String(10), nullable=True)

    tp_hit = Column(Boolean, default=False)
    tp_order_id = Column(String)
    tp_executed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime)
    filled_at = Column(DateTime)
    cancelled_at = Column(DateTime)

    group = relationship("PositionGroup", back_populates="dca_orders", lazy="noload")
    pyramid = relationship("Pyramid", back_populates="dca_orders", lazy="noload")
