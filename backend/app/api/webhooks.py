from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.signature_validation import validate_signature
from app.db.database import get_db_session
from app.schemas.webhook_payloads import TradingViewSignal as WebhookPayload
from app.services.signal_router import SignalRouterService

router = APIRouter()

@router.post("/tradingview", status_code=status.HTTP_200_OK)
async def tradingview_webhook(
    payload: WebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    is_signature_valid: bool = Depends(validate_signature),
):
    """
    Receives a webhook from TradingView, validates it, and routes it.
    """
    if not is_signature_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature.",
        )

    signal_router = SignalRouterService()
    result = await signal_router.route(payload, db)

    return {"status": "success", "result": result}