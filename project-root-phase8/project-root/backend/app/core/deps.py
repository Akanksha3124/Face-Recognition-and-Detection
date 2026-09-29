"""
Shared FastAPI dependencies for authentication and authorization.

get_current_user validates the access token and loads the user fresh
from the database on every request. require_roles() builds on top of
it to gate a route to specific roles.

Deliberate design choice: authorization checks the user's role from
the database, not the `role` claim embedded in the JWT. The claim is
there for the frontend's convenience (avoids an extra request just to
know the role), but trusting it server-side would mean a role change
or account deactivation doesn't take effect until the access token
expires (~30 min). Checking the DB costs one extra query per request
but means access is revoked immediately.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User
from app.repositories.user_repository import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(token)
    except ValueError:
        raise _credentials_exception
    if payload.get("type") != "access":
        raise _credentials_exception
    subject = payload.get("sub")
    if subject is None:
        raise _credentials_exception

    user = await get_user_by_id(db, int(subject))
    if user is None or not user.is_active:
        raise _credentials_exception
    return user


def require_roles(*allowed_roles: str):
    """Dependency factory: `Depends(require_roles("ADMIN", "VERIFIER"))`."""

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return _check
