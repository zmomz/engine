"""
API Key authentication for the mock exchange.
Mimics Binance HMAC-SHA256 signature verification.
"""
import hmac
import hashlib
import time
from typing import Optional, Tuple
from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from models import APIKey


def verify_signature(
    api_secret: str,
    query_string: str,
    provided_signature: str
) -> bool:
    """
    Verify HMAC-SHA256 signature like Binance does.
    """
    expected_signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, provided_signature)


def authenticate_request(
    db: Session,
    api_key: Optional[str],
    signature: Optional[str] = None,
    query_string: str = "",
    require_signature: bool = False
) -> Tuple[bool, Optional[APIKey], str]:
    """
    Authenticate an API request.

    Args:
        db: Database session
        api_key: The X-MBX-APIKEY header value
        signature: The signature query parameter (for signed endpoints)
        query_string: The query string for signature verification
        require_signature: Whether this endpoint requires a signature

    Returns:
        Tuple of (success, api_key_obj, error_message)
    """
    if not api_key:
        return False, None, "API key required"

    # Look up API key
    key_obj = db.query(APIKey).filter(
        APIKey.api_key == api_key,
        APIKey.is_active == True
    ).first()

    if not key_obj:
        return False, None, "Invalid API key"

    # For signed endpoints, verify signature
    if require_signature:
        if not signature:
            return False, None, "Signature required"

        # Remove signature from query string for verification
        params_to_sign = query_string.replace(f"&signature={signature}", "")
        params_to_sign = params_to_sign.replace(f"signature={signature}&", "")
        params_to_sign = params_to_sign.replace(f"signature={signature}", "")

        if not verify_signature(key_obj.api_secret, params_to_sign, signature):
            return False, None, "Invalid signature"

    return True, key_obj, ""


async def get_api_key_from_request(request: Request, db: Session) -> APIKey:
    """
    FastAPI dependency to extract and validate API key from request.
    """
    api_key = request.headers.get("X-MBX-APIKEY")

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_obj = db.query(APIKey).filter(
        APIKey.api_key == api_key,
        APIKey.is_active == True
    ).first()

    if not key_obj:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return key_obj


def create_signature(api_secret: str, params: dict) -> str:
    """
    Create a signature for a request (helper for testing).
    """
    # Add timestamp if not present
    if 'timestamp' not in params:
        params['timestamp'] = int(time.time() * 1000)

    # Build query string
    query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])

    # Create signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature
