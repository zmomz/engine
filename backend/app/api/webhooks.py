from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.signature_validation import SignatureValidator
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.webhook_payloads import WebhookPayload
from app.services.signal_router import SignalRouterService

router = APIRouter()

@router.post("/{user_id}/tradingview", status_code=status.HTTP_202_ACCEPTED)
async def tradingview_webhook(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(SignatureValidator()),
):
    """
    Receives a webhook from TradingView, validates it, and routes it.
    The user is authenticated via the SignatureValidator dependency.
    """
    # The payload is parsed and validated within the SignatureValidator
    payload = await request.json()
    webhook_payload = WebhookPayload(**payload)

    # Pass the authenticated user to the service layer
    signal_router = SignalRouterService(user=user)
    result = await signal_router.route(webhook_payload, db)

    return {"status": "success", "message": "Signal received and is being processed.", "result": result}