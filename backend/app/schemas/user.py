import uuid
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, EmailStr, model_validator, field_validator
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig # Import config schemas
from app.schemas.telegram_config import TelegramConfig

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    webhook_secret: Optional[str] = None
    risk_config: Optional[RiskEngineConfig] = None
    secure_signals: Optional[bool] = True  # When False, webhook secret validation is skipped

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
    key_target_exchange: Optional[str] = None # Target exchange for key updates
    testnet: Optional[bool] = None # Added for input
    account_type: Optional[str] = None # Added for input
    risk_config: Optional[RiskEngineConfig] = None
    telegram_config: Optional[Dict[str, Any]] = None
    secure_signals: Optional[bool] = None  # Toggle webhook secret validation

class UserInDB(UserBase):
    id: uuid.UUID
    hashed_password: str
    encrypted_api_keys: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

    # Add a validator to convert dca_grid_config from dict to DCAGridConfig on read
    @model_validator(mode='before')
    @classmethod
    def validate_configs(cls, data: Any):
        if isinstance(data, dict):
            pass
        return data

class UserRead(UserBase):
    id: uuid.UUID
    risk_config: Optional[RiskEngineConfig] = None
    telegram_config: Optional[Dict[str, Any]] = None
    encrypted_api_keys: Optional[Dict[str, Any]] = None # Explicitly include to pass to validator
    configured_exchange_details: Optional[Dict[str, Dict[str, Any]]] = None # Detailed exchange configs
    configured_exchanges: List[str] = [] # List of configured exchange names

    class Config:
        from_attributes = True

    # Add a validator to convert dca_grid_config from dict to DCAGridConfig on read
    @model_validator(mode='before')
    @classmethod
    def validate_configs(cls, data: Any):
        if isinstance(data, dict):
            if "risk_config" in data and isinstance(data["risk_config"], dict):
                data["risk_config"] = RiskEngineConfig.model_validate(data["risk_config"])
            
            # Populate configured_exchange_details from encrypted_api_keys
            if "encrypted_api_keys" in data and isinstance(data["encrypted_api_keys"], dict):
                details = {}
                configured_exchanges_list = []
                for exchange_name, config in data["encrypted_api_keys"].items():
                    if isinstance(config, dict):
                        exchange_detail = {
                            "testnet": config.get("testnet", False),
                            "account_type": config.get("account_type", "UNIFIED") 
                        }
                        details[exchange_name] = exchange_detail
                        configured_exchanges_list.append(exchange_name)
                data["configured_exchange_details"] = details
                data["configured_exchanges"] = configured_exchanges_list
            else:
                data["configured_exchange_details"] = {}
                data["configured_exchanges"] = []

        return data

    @field_validator('risk_config', mode='before')
    @classmethod
    def set_risk_defaults(cls, v):
        if isinstance(v, dict):
            return RiskEngineConfig.model_validate(v)
        return v