
import hashlib
import hmac
import time

def generate_tradingview_signature(payload: str, secret: str) -> str:
    """
    Generates a simple HMAC-SHA256 signature.
    """
    signature = hmac.new(
        bytes(secret, 'utf-8'),
        msg=bytes(payload, 'utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    return signature
