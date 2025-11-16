import hmac
import hashlib
from fastapi import Request, HTTPException, status

async def validate_signature(request: Request):
    """
    Validates the TradingView webhook signature.
    """
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature.",
        )

    body = await request.body()
    secret = "your-super-secret-key"  # This should match the secret in your .env file
    expected_signature = hmac.new(
        key=secret.encode(), msg=body, digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature.",
        )

    return True