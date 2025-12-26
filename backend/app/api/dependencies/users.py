from typing import Optional
import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.core.security import SECRET_KEY, ALGORITHM
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

# Make token optional to support both header and cookie auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/login", auto_error=False)

COOKIE_NAME = "access_token"


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract token from httpOnly cookie."""
    cookie_value = request.cookies.get(COOKIE_NAME)
    if cookie_value and cookie_value.startswith("Bearer "):
        return cookie_value[7:]  # Remove "Bearer " prefix
    return None


async def check_token_blacklist(jti: str) -> bool:
    """
    Check if a token is blacklisted.

    Returns:
        True if token is blacklisted (invalid), False if valid
    """
    try:
        cache = await get_cache()
        return await cache.is_token_blacklisted(jti)
    except Exception as e:
        # If Redis is unavailable, allow the token (fail open for availability)
        logger.warning(f"Token blacklist check failed: {e}")
        return False


async def get_current_user(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_revoked_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token has been revoked",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try header token first, then cookie
    token = header_token or get_token_from_cookie(request)

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")

        if username is None:
            raise credentials_exception

        # Check if token is blacklisted (for secure logout)
        if jti:
            is_blacklisted = await check_token_blacklist(jti)
            if is_blacklisted:
                logger.info(f"Rejected blacklisted token {jti[:8]}...")
                raise token_revoked_exception

    except JWTError:
        raise credentials_exception

    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user
