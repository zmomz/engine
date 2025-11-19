from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "YOUR_SECRET_KEY"  # TODO: Load from environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    print(f"Password length before hashing: {len(password)}")
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

        # TODO: Initialize Fernet with a key from environment variables

        self.fernet = None



    def encrypt_keys(self, api_key: str, secret_key: str) -> dict:

        # TODO: Implement actual encryption

        return {"encrypted_data": "placeholder"}



    def decrypt_keys(self, encrypted_data: dict) -> tuple[str, str]:

        # TODO: Implement actual decryption

        return "decrypted_api_key", "decrypted_secret_key"
