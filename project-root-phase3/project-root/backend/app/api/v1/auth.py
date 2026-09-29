"""
Authentication routes. Thin by design — each handler validates input
(via the Pydantic schema), calls into app/services/auth_service.py,
translates the service's exceptions into HTTP status codes, and
returns. No business logic lives here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import User
from app.schemas.auth import (
    AdminRegisterRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import auth_service

router = APIRouter()


def _to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, role=user.role.name, is_active=user.is_active)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserOut:
    try:
        user = await auth_service.register_user(db, payload.email, payload.password, payload.role.value)
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    except auth_service.RoleNotFound:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Required role is not seeded")
    await db.commit()
    return _to_user_out(user)


@router.post("/register-admin", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_admin(
    payload: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("ADMIN")),
) -> UserOut:
    """Admin-only: can create an account with any role, including ADMIN.
    Public /register cannot — see schemas/auth.py for why."""
    try:
        user = await auth_service.register_user(db, payload.email, payload.password, payload.role)
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    except auth_service.RoleNotFound:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown role: {payload.role}")
    await db.commit()
    return _to_user_out(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        user = await auth_service.authenticate_user(db, payload.email, payload.password)
    except auth_service.InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    access_token, refresh_token = await auth_service.issue_token_pair(db, user)
    await db.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        access_token, refresh_token = await auth_service.refresh_token_pair(db, payload.refresh_token)
    except auth_service.InvalidRefreshToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    await db.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)) -> None:
    await auth_service.logout(db, payload.refresh_token)
    await db.commit()


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _to_user_out(current_user)
