import hashlib
import hmac
import time

from app.config import settings


def sign_artifact_url(path: str, expiry_seconds: int = 7 * 24 * 3600) -> str:
    exp = int(time.time()) + expiry_seconds
    sig = _compute_sig(path, str(exp))
    return f"{path}?sig={sig}&exp={exp}"


def verify_artifact_url(path: str, sig: str, exp: str) -> bool:
    try:
        if int(exp) < int(time.time()):
            return False
        expected = _compute_sig(path, exp)
        return hmac.compare_digest(sig, expected)
    except (ValueError, TypeError):
        return False


def _compute_sig(path: str, exp: str) -> str:
    msg = f"{path}:{exp}".encode()
    key = settings.artifact_signing_key.encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
