from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
import logging

from app.db.database import get_db_session
from app.schemas.user import UserCreate, UserInDB, UserRead
from app.repositories.user import UserRepository
from app.core.security import (
    get_password_hash,
    create_access_token,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_token_jti,
    get_token_expiry_seconds
)
from app.core.config import settings
from app.core.cache import get_cache
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Cookie settings for security
COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds


def set_auth_cookie(response: Response, token: str, max_age: int = None):
    """Set httpOnly cookie with the access token."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=f"Bearer {token}",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",  # HTTPS only in production
        samesite="lax",
        max_age=max_age or COOKIE_MAX_AGE,
        path="/",
    )


def clear_auth_cookie(response: Response):
    """Clear the auth cookie on logout."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


def get_token_from_cookie(request: Request) -> str | None:
    """Extract token from httpOnly cookie."""
    cookie_value = request.cookies.get(COOKIE_NAME)
    if cookie_value and cookie_value.startswith("Bearer "):
        return cookie_value[7:]
    return None


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db_session),
):
    user_repo = UserRepository(db)
    existing_user = await user_repo.get_by_username(user_in.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    existing_email = await user_repo.get_by_email(user_in.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = get_password_hash(user_in.password)
    user = await user_repo.create(user_in, hashed_password)
    return user


@router.post("/login")
@limiter.limit("10/minute")
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, jti, expires_in = create_access_token(data={"sub": user.username})

    # Set httpOnly cookie with the actual expiry time
    set_auth_cookie(response, access_token, max_age=expires_in)

    # Also return token in body for backward compatibility during migration
    return {"access_token": access_token, "token_type": "bearer", "user": UserRead.from_orm(user)}


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Logout the user by:
    1. Adding the token to the blacklist (if Redis available)
    2. Clearing the auth cookie
    """
    # Get the token from cookie to blacklist it
    token = get_token_from_cookie(request)

    if token:
        # Get the JTI and remaining expiry time
        jti = get_token_jti(token)
        expiry_seconds = get_token_expiry_seconds(token)

        if jti and expiry_seconds > 0:
            try:
                cache = await get_cache()
                # Blacklist the token until it would have expired anyway
                await cache.blacklist_token(jti, expiry_seconds)
                logger.info(f"Token {jti[:8]}... blacklisted for {expiry_seconds} seconds")
            except Exception as e:
                # Log but don't fail - cookie will still be cleared
                logger.warning(f"Failed to blacklist token: {e}")

    # Always clear the cookie
    clear_auth_cookie(response)
    return {"message": "Successfully logged out"}
