from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os
import json
import uuid
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

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> Tuple[str, str, int]:
    """
    Create a JWT access token with a unique JTI.

    Returns:
        Tuple of (encoded_jwt, jti, expires_in_seconds)
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        expires_in_seconds = int(expires_delta.total_seconds())
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_in_seconds = ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # Generate unique token ID for blacklisting support
    jti = str(uuid.uuid4())

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": jti
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt, jti, expires_in_seconds


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


def get_token_jti(token: str) -> Optional[str]:
    """Extract JTI from a token without full validation."""
    payload = decode_token(token)
    if payload:
        return payload.get("jti")
    return None


def get_token_expiry_seconds(token: str) -> int:
    """Get remaining seconds until token expires."""
    payload = decode_token(token)
    if payload and "exp" in payload:
        exp_timestamp = payload["exp"]
        remaining = exp_timestamp - datetime.utcnow().timestamp()
        return max(0, int(remaining))
    return 0



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
