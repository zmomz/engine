from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm

from app.db.database import get_db_session
from app.schemas.user import UserCreate, UserInDB, UserRead
from app.repositories.user import UserRepository
from app.core.security import get_password_hash, create_access_token, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core.config import settings
from app.rate_limiter import limiter

router = APIRouter()

# Cookie settings for security
COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds


def set_auth_cookie(response: Response, token: str):
    """Set httpOnly cookie with the access token."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=f"Bearer {token}",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",  # HTTPS only in production
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def clear_auth_cookie(response: Response):
    """Clear the auth cookie on logout."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


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
    access_token = create_access_token(data={"sub": user.username})

    # Set httpOnly cookie
    set_auth_cookie(response, access_token)

    # Also return token in body for backward compatibility during migration
    return {"access_token": access_token, "token_type": "bearer", "user": UserRead.from_orm(user)}


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    clear_auth_cookie(response)
    return {"message": "Successfully logged out"}
