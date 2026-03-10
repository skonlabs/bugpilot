import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()


def _get_fernet() -> Fernet:
    key = settings.FERNET_KEY
    if not key:
        key = Fernet.generate_key().decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def hash_secret(secret: str) -> str:
    """Hash a secret using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(secret.encode(), salt).decode()


def verify_secret(secret: str, hashed: str) -> bool:
    """Verify a secret against its bcrypt hash."""
    try:
        return bcrypt.checkpw(secret.encode(), hashed.encode())
    except Exception:
        return False


def encrypt_credentials(data: dict) -> bytes:
    """Encrypt credentials dict using Fernet symmetric encryption."""
    import json
    fernet = _get_fernet()
    return fernet.encrypt(json.dumps(data).encode())


def decrypt_credentials(ciphertext: bytes) -> dict:
    """Decrypt Fernet-encrypted credentials."""
    import json
    fernet = _get_fernet()
    return json.loads(fernet.decrypt(ciphertext).decode())


class TokenPayload(BaseModel):
    sub: str  # user_id
    org_id: str
    device_fp: str
    role: str
    exp: int
    jti: str


def create_session_token(
    user_id: str,
    org_id: str,
    device_fp: str,
    role: str,
) -> tuple[str, str, str, str]:
    """
    Returns (jwt_token, refresh_token, token_hash, refresh_hash)
    """
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "org_id": org_id,
        "device_fp": device_fp,
        "role": role,
        "exp": int(expires_at.timestamp()),
        "jti": jti,
    }
    jwt_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    refresh_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(jwt_token.encode()).hexdigest()
    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    return jwt_token, refresh_token, token_hash, refresh_hash


def verify_session_token(token: str) -> Optional[TokenPayload]:
    """Decode and verify JWT token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return TokenPayload(**payload)
    except JWTError:
        return None


def hash_token(token: str) -> str:
    """SHA-256 hash of a token string."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_hmac_sha256(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()  # noqa: E501
    return hmac.compare_digest(expected, signature.lstrip("sha256=").lstrip("v1="))
