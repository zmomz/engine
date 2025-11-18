import uuid
from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    webhook_secret: Optional[str] = None
    encrypted_api_keys: Optional[Dict[str, Any]] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    webhook_secret: Optional[str] = None
    encrypted_api_keys: Optional[Dict[str, Any]] = None

class UserInDB(UserBase):
    id: uuid.UUID
    hashed_password: str

    class Config:
        from_attributes = True

class UserRead(UserBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

