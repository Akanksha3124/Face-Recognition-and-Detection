"""
Password hashing and JWT helpers.

Access tokens are short-lived (ACCESS_TOKEN_EXPIRE_MINUTES) and carry a
`role` claim for convenience (e.g. the frontend can read it without an
extra request) — but authorization decisions server-side never trust
that claim; app/core/deps.py re-checks the role against the database on
every request, so a role change or account deactivation takes effect
immediately rather than only after the token expires.

Refresh tokens are longer-lived and are additionally tracked in the
`refresh_tokens` table (by hash, never plaintext) so they can be
revoked on logout or rotated on use — a bare JWT can't be revoked
before it expires, which is why this extra bit of state exists.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta: timedelta, extra_claims: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        # Without a unique-per-token claim, two tokens issued for the same
        # subject within the same second (second-resolution exp/iat) are
        # byte-identical — which broke refresh-token storage, since that
        # table has a uniqueness constraint on the token's hash. jti fixes
        # that and is also standard practice for revocable JWTs.
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), {"role": role}
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict:
    """Raises ValueError on any invalid/expired/malformed token."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError(str(exc)) from exc


def hash_token(token: str) -> str:
    """SHA-256 hex digest, used to store refresh tokens without keeping the plaintext."""
    return hashlib.sha256(token.encode()).hexdigest()
