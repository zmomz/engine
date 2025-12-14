import hmac
import hashlib
import logging
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db_session
from app.repositories.user import UserRepository
from app.schemas.webhook_payloads import WebhookPayload

logger = logging.getLogger(__name__)


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
        client_ip = request.client.host if request.client else "unknown"

        # We need to parse the body to get the secret inside the payload
        try:
            # Parse the JSON body. We use request.json() which caches the result
            # so subsequent calls in the endpoint won't fail.
            payload = await request.json()
        except Exception:
            logger.warning(f"Webhook auth failed: Invalid JSON payload from IP {client_ip} for user_id {user_id}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON payload.",
            )

        received_secret = payload.get("secret")
        if not received_secret:
            logger.warning(f"Webhook auth failed: Missing secret from IP {client_ip} for user_id {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing secret in payload.",
            )

        user = await user_repo.get_by_id(user_id)
        if not user:
            logger.warning(f"Webhook auth failed: User not found for user_id {user_id} from IP {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        # Validate the secret
        # Use hmac.compare_digest to prevent timing attacks
        if not hmac.compare_digest(user.webhook_secret, received_secret):
            logger.warning(f"Webhook auth failed: Invalid secret for user {user.username} (ID: {user_id}) from IP {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid secret.",
            )

        # Attach user to request state for later use
        request.state.user = user
        return user