import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    JSON,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.types import GUID
from app.models.base import Base

class EntryOrderType(str, PyEnum):
    LIMIT = "limit"
    MARKET = "market"

class TakeProfitMode(str, PyEnum):
    PER_LEG = "per_leg"
    AGGREGATE = "aggregate"
    HYBRID = "hybrid"

class DCAConfiguration(Base):
    """
    Stores specific DCA strategy configurations for a [Pair/Timeframe/Exchange] combination.
    """
    __tablename__ = "dca_configurations"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    
    # Composite Key Fields
    pair = Column(String, nullable=False)      # e.g., "BTC/USDT"
    timeframe = Column(Integer, nullable=False) # e.g., 15, 60 (in minutes)
    exchange = Column(String, nullable=False)  # e.g., "binance"
    
    # Strategy Settings
    entry_order_type = Column(
        SQLAlchemyEnum(EntryOrderType, name="entry_order_type_enum", values_callable=lambda x: [e.value for e in x]),
        default=EntryOrderType.LIMIT,
        nullable=False
    )
    
    # Stores the list of levels: [{distance: 1.0, quantity: 10.0, tp: 2.0}, ...]
    dca_levels = Column(JSON, nullable=False, default=list)
    
    # New: Specific levels per pyramid index {"1": [...], "2": [...]}
    pyramid_specific_levels = Column(JSON, nullable=False, default=dict)
    
    tp_mode = Column(
        SQLAlchemyEnum(TakeProfitMode, name="take_profit_mode_enum", values_callable=lambda x: [e.value for e in x]),
        default=TakeProfitMode.PER_LEG,
        nullable=False
    )
    
    # Flexible storage for mode-specific TP settings (aggregate_tp)
    # Example: {"aggregate_tp_percent": 10.0}
    tp_settings = Column(JSON, nullable=False, default=dict)
    
    max_pyramids = Column(Integer, default=5, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="dca_configurations")

    __table_args__ = (
        UniqueConstraint('user_id', 'pair', 'timeframe', 'exchange', name='uix_user_pair_timeframe_exchange'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "pair": self.pair,
            "timeframe": self.timeframe,
            "exchange": self.exchange,
            "entry_order_type": self.entry_order_type.value if isinstance(self.entry_order_type, PyEnum) else self.entry_order_type,
            "dca_levels": self.dca_levels,
            "pyramid_specific_levels": self.pyramid_specific_levels,
            "tp_mode": self.tp_mode.value if isinstance(self.tp_mode, PyEnum) else self.tp_mode,
            "tp_settings": self.tp_settings,
            "max_pyramids": self.max_pyramids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
