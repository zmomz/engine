import uuid
import logging
from fastapi import APIRouter, Depends, status, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.api.dependencies.signature_validation import SignatureValidator
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.webhook_payloads import WebhookPayload
from app.services.signal_router import SignalRouterService
from app.core.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter()

# Lock timeout for webhook processing (30 seconds)
WEBHOOK_LOCK_TTL = 30


@router.post("/{user_id}/tradingview", status_code=status.HTTP_202_ACCEPTED)
async def tradingview_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(SignatureValidator()),
):
    """
    Receives a webhook from TradingView, validates it, and routes it.
    The user is authenticated via the SignatureValidator dependency.

    Uses distributed locking to prevent race conditions when multiple
    webhooks arrive simultaneously for the same symbol/timeframe.
    """
    # The payload is parsed and validated within the SignatureValidator
    payload = await request.json()
    try:
        webhook_payload = WebhookPayload(**payload)
    except ValidationError as e:
        raise RequestValidationError(e.errors())

    # SPOT TRADING: Reject short signals early
    # Short signals (sell action without exit intent) are not supported in spot trading
    intent_type = webhook_payload.execution_intent.type.lower() if webhook_payload.execution_intent else "signal"
    action = webhook_payload.tv.action.lower()

    if action == "sell" and intent_type != "exit":
        logger.warning(
            f"Short signal rejected for {webhook_payload.tv.symbol} "
            f"(user: {user.id}). Spot trading does not support short positions."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Signal rejected: Spot trading does not support short positions. Use execution_intent.type='exit' to close a long position."
        )

    # Create a lock key based on user + symbol + timeframe + side
    # This prevents race conditions for the same position
    # For SPOT trading: All positions are "long" (we buy to enter, sell to exit)
    side = "long"

    lock_resource = f"webhook:{user.id}:{webhook_payload.tv.symbol}:{webhook_payload.tv.timeframe}:{side}"
    lock_id = str(uuid.uuid4())

    # Try to acquire distributed lock
    cache = await get_cache()
    lock_acquired = await cache.acquire_lock(lock_resource, lock_id, WEBHOOK_LOCK_TTL)

    if not lock_acquired:
        logger.warning(
            f"Webhook lock contention for {webhook_payload.tv.symbol} "
            f"(user: {user.id}, timeframe: {webhook_payload.tv.timeframe}). "
            f"Another webhook is being processed."
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another webhook for this symbol/timeframe is currently being processed. Please retry."
        )

    try:
        # Pass the authenticated user to the service layer
        signal_router = SignalRouterService(user=user)
        result = await signal_router.route(webhook_payload, db)

        return {"status": "success", "message": "Signal received and is being processed.", "result": result}

    finally:
        # Always release the lock
        released = await cache.release_lock(lock_resource, lock_id)
        if not released:
            logger.warning(f"Failed to release webhook lock for {lock_resource}")
