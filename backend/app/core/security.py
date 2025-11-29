from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
import os
import json
from cryptography.fernet import Fernet

from jose import jwt
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SECRET_KEY is validated in settings
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):

    to_encode = data.copy()

    if expires_delta:

        expire = datetime.utcnow() + expires_delta

    else:

        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt



class EncryptionService:

    def __init__(self):
        # ENCRYPTION_KEY is validated in settings
        self.fernet = Fernet(settings.ENCRYPTION_KEY)

    def encrypt_keys(self, api_key: str, secret_key: str) -> dict:
        data = json.dumps({"api_key": api_key, "secret_key": secret_key}).encode()
        encrypted_data = self.fernet.encrypt(data)
        return {"encrypted_data": encrypted_data.decode()}

    def decrypt_keys(self, encrypted_data: str | dict) -> tuple[str, str]:
        # Handle both direct string and dictionary formats for encrypted_data
        if isinstance(encrypted_data, dict):
            token = encrypted_data.get("encrypted_data")
            if not token:
                raise ValueError("Invalid encrypted data format: 'encrypted_data' key missing in dictionary")
        elif isinstance(encrypted_data, str):
            token = encrypted_data
        else:
            raise ValueError(f"Unsupported encrypted data type: {type(encrypted_data)}")
            
        decrypted_bytes = self.fernet.decrypt(token.encode())
        data = json.loads(decrypted_bytes.decode())
        return data["api_key"], data["secret_key"]
