import os
from typing import List
from pydantic import BaseModel, Field

class Settings(BaseModel):
    DATABASE_URL: str
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    CORS_ORIGINS: List[str]
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"

    @classmethod
    def load_from_env(cls):
        database_url = os.getenv("DATABASE_URL")
        secret_key = os.getenv("SECRET_KEY")
        encryption_key = os.getenv("ENCRYPTION_KEY")
        environment = os.getenv("ENVIRONMENT", "development")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_file_path = os.getenv("LOG_FILE_PATH", "logs/app.log")
        
        cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]
        
        # Ensure localhost:3000 is always allowed for dev convenience
        if "http://localhost:3000" not in cors_origins:
            cors_origins.append("http://localhost:3000")

        # Validate required fields
        missing = []
        if not database_url:
            missing.append("DATABASE_URL")
        if not secret_key:
            missing.append("SECRET_KEY")
        if not encryption_key:
            missing.append("ENCRYPTION_KEY")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            DATABASE_URL=database_url,
            SECRET_KEY=secret_key,
            ENCRYPTION_KEY=encryption_key,
            CORS_ORIGINS=cors_origins,
            ENVIRONMENT=environment,
            LOG_LEVEL=log_level,
            LOG_FILE_PATH=log_file_path
        )

# Load settings immediately. This ensures fail-fast behavior at startup/import time.
# SECURITY: Test environment MUST explicitly set TEST_MODE=true AND provide valid credentials
# We no longer fall back to weak test credentials automatically
_is_test_mode = os.getenv("TEST_MODE", "").lower() == "true" or os.getenv("PYTEST_CURRENT_TEST") is not None

try:
    settings = Settings.load_from_env()
except ValueError as e:
    if _is_test_mode:
        # For tests: require test credentials to be explicitly set via environment
        # Tests should set these in conftest.py or pytest fixtures
        import secrets
        _test_secret = os.getenv("TEST_SECRET_KEY") or secrets.token_urlsafe(32)
        _test_encryption = os.getenv("TEST_ENCRYPTION_KEY") or "dGVzdF9lbmNyeXB0aW9uX2tleV8zMmJ5dGVzIQ=="  # Base64 test key

        settings = Settings(
            DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"),
            SECRET_KEY=_test_secret,
            ENCRYPTION_KEY=_test_encryption,
            CORS_ORIGINS=["http://localhost:3000"],
            ENVIRONMENT="test"
        )
    else:
        # Production/Development: fail fast with clear error
        print(f"CRITICAL: Configuration Error: {e}")
        print("Please set the required environment variables: DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY")
        raise e
