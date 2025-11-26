import hmac
import hashlib
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db_session
from app.repositories.user import UserRepository
from app.schemas.webhook_payloads import WebhookPayload

async def get_webhook_payload(request: Request) -> WebhookPayload:
    try:
        json_body = await request.json()
        return WebhookPayload(**json_body)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid webhook payload.",
        )

class SignatureValidator:
    async def __call__(self, user_id: str, request: Request, db_session: AsyncSession = Depends(get_db_session)):
        user_repo = UserRepository(db_session)
        
        # We need to parse the body to get the secret inside the payload
        try:
            # Parse the JSON body. We use request.json() which caches the result 
            # so subsequent calls in the endpoint won't fail.
            payload = await request.json()
        except Exception:
             raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON payload.",
            )

        received_secret = payload.get("secret")
        if not received_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing secret in payload.",
            )

        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        # Validate the secret
        # Use hmac.compare_digest to prevent timing attacks
        if not hmac.compare_digest(user.webhook_secret, received_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid secret.",
            )
        
        # Attach user to request state for later use
        request.state.user = user
        return user