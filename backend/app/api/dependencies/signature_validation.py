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
    async def __call__(self, user_id: str, request: Request, payload: WebhookPayload = Depends(get_webhook_payload), db_session: AsyncSession = Depends(get_db_session)):
        user_repo = UserRepository(db_session)
        signature = request.headers.get("X-Signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing signature.",
            )

        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        body = await request.body()
        secret = user.webhook_secret
        expected_signature = hmac.new(
            key=secret.encode(), msg=body, digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid signature.",
            )
        
        # Attach user to request state for later use
        request.state.user = user
        return user