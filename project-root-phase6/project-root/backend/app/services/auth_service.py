"""
Auth business logic. Routes stay thin (validate → call this → return);
everything that decides *whether* an operation is allowed lives here,
not in app/api/v1/auth.py.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import User
from app.repositories.refresh_token_repository import (
    get_refresh_token_by_hash,
    revoke_refresh_token,
    store_refresh_token,
)
from app.repositories.user_repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
    get_user_by_id,
)


class EmailAlreadyRegistered(Exception):
    pass


class RoleNotFound(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidRefreshToken(Exception):
    pass


async def register_user(db: AsyncSession, email: str, password: str, role_name: str) -> User:
    if await get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegistered(email)
    role = await get_role_by_name(db, role_name)
    if role is None:
        raise RoleNotFound(role_name)
    return await create_user(db, email=email, password_hash=hash_password(password), role_id=role.id)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        # Deliberately identical error for "no such user" and "wrong
        # password" — distinguishing them lets an attacker enumerate
        # registered emails.
        raise InvalidCredentials()
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> tuple[str, str]:
    access_token = create_access_token(subject=str(user.id), role=user.role.name)
    refresh_token = create_refresh_token(subject=str(user.id))
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await store_refresh_token(db, user_id=user.id, token_hash=hash_token(refresh_token), expires_at=expires_at)
    return access_token, refresh_token


async def refresh_token_pair(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise InvalidRefreshToken()
    if payload.get("type") != "refresh":
        raise InvalidRefreshToken()

    stored = await get_refresh_token_by_hash(db, hash_token(refresh_token))
    if stored is None or stored.revoked or stored.expires_at < datetime.now(timezone.utc):
        raise InvalidRefreshToken()

    user = await get_user_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise InvalidRefreshToken()

    # Rotation: the presented refresh token is single-use. Revoking it
    # here means a stolen-and-replayed old refresh token fails even if
    # the legitimate client already rotated past it.
    await revoke_refresh_token(db, stored)
    return await issue_token_pair(db, user)


async def logout(db: AsyncSession, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return  # already invalid/expired — nothing to revoke
    if payload.get("type") != "refresh":
        return
    stored = await get_refresh_token_by_hash(db, hash_token(refresh_token))
    if stored is not None and not stored.revoked:
        await revoke_refresh_token(db, stored)
