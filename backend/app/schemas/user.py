import uuid
from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig # Import config schemas

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    webhook_secret: Optional[str] = None
    encrypted_api_keys: Optional[Dict[str, Any]] = None
    exchange: Optional[str] = None # Added exchange to UserBase for update
    risk_config: Optional[RiskEngineConfig] = None
    dca_grid_config: Optional[DCAGridConfig] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    webhook_secret: Optional[str] = None
    encrypted_api_keys: Optional[Dict[str, Any]] = None
    api_key: Optional[str] = None # Added for input
    secret_key: Optional[str] = None # Added for input
    exchange: Optional[str] = None
    risk_config: Optional[RiskEngineConfig] = None
    dca_grid_config: Optional[DCAGridConfig] = None

class UserInDB(UserBase):
    id: uuid.UUID
    hashed_password: str

    class Config:
        from_attributes = True

class UserRead(UserBase):
    id: uuid.UUID
    exchange: str # Ensure exchange is returned
    risk_config: RiskEngineConfig
    dca_grid_config: DCAGridConfig

    class Config:
        from_attributes = True
