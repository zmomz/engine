import uuid
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, EmailStr, model_validator
from app.schemas.grid_config import RiskEngineConfig, DCAGridConfig # Import config schemas

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    webhook_secret: Optional[str] = None
    exchange: Optional[str] = None # Added exchange to UserBase for update
    risk_config: Optional[RiskEngineConfig] = None
    dca_grid_config: Optional[Dict[str, Any]] = None # Stored as JSON dict

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
    key_target_exchange: Optional[str] = None # Explicit target for key updates
    testnet: Optional[bool] = None # Added for input
    account_type: Optional[str] = None # Added for input
    risk_config: Optional[RiskEngineConfig] = None
    dca_grid_config: Optional[Dict[str, Any]] = None # Expects JSON dict

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
            if "dca_grid_config" in data and isinstance(data["dca_grid_config"], dict):
                data["dca_grid_config"] = DCAGridConfig.model_validate(data["dca_grid_config"])
        return data

class UserRead(UserBase):
    id: uuid.UUID
    exchange: Optional[str] = None
    risk_config: Optional[RiskEngineConfig] = None
    dca_grid_config: Optional[DCAGridConfig] = None # Now a pydantic model after validation
    configured_exchange_details: Optional[Dict[str, Dict[str, Any]]] = None # Detailed exchange configs
    configured_exchanges: List[str] = [] # List of configured exchange names

    class Config:
        from_attributes = True

    # Add a validator to convert dca_grid_config from dict to DCAGridConfig on read
    @model_validator(mode='before')
    @classmethod
    def validate_configs(cls, data: Any):
        if isinstance(data, dict):
            if "dca_grid_config" in data and isinstance(data["dca_grid_config"], dict):
                data["dca_grid_config"] = DCAGridConfig.model_validate(data["dca_grid_config"])
            if "risk_config" in data and isinstance(data["risk_config"], dict):
                data["risk_config"] = RiskEngineConfig.model_validate(data["risk_config"])
            
            # Populate configured_exchange_details from encrypted_api_keys
            if "encrypted_api_keys" in data and isinstance(data["encrypted_api_keys"], dict):
                details = {}
                for exchange_name, config in data["encrypted_api_keys"].items():
                    if isinstance(config, dict):
                        exchange_detail = {
                            "testnet": config.get("testnet", False),
                            "account_type": config.get("account_type", "UNIFIED") # Default for Bybit
                        }
                        # For Binance, default_type is already 'spot' and is not dynamically set from here.
                        # We could add 'default_type' to config if it ever became user configurable per exchange.
                        details[exchange_name] = exchange_detail
                data["configured_exchange_details"] = details
                data["configured_exchanges"] = list(data["encrypted_api_keys"].keys())

        return data
