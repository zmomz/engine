import uuid
import secrets
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship

from app.db.types import GUID
from app.models.base import Base
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig # Import config schemas

def generate_webhook_secret():
    return secrets.token_hex(16)

class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    exchange = Column(String, default="binance", nullable=False)
    webhook_secret = Column(String, nullable=False, default=generate_webhook_secret)
    encrypted_api_keys = Column(JSON, nullable=True)
    
    # User-specific risk and grid configurations
    risk_config = Column(JSON, nullable=False, default=RiskEngineConfig().model_dump(mode='json')) # Store as JSON
    dca_grid_config = Column(JSON, nullable=False, default=DCAGridConfig([]).model_dump(mode='json')) # Store as JSON

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    position_groups = relationship("PositionGroup", backref="user", lazy="noload")
    queued_signals = relationship("QueuedSignal", backref="user", lazy="noload")
