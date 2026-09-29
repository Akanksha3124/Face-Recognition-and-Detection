"""
Auth request/response schemas.

RegisterRequest.role is deliberately restricted to the three
non-administrative roles — public self-registration can never grant
ADMIN. Creating an ADMIN account (or any account via an already-
privileged operator) goes through /auth/register-admin instead, which
requires an authenticated ADMIN caller. This is a security decision,
not an oversight: this platform handles sensitive case data, so the
highest-privilege role should never be reachable from an anonymous
HTTP request.
"""
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class PublicRole(str, Enum):
    INVESTIGATOR = "INVESTIGATOR"
    DISASTER_RESPONDER = "DISASTER_RESPONDER"
    VERIFIER = "VERIFIER"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: PublicRole


class AdminRegisterRequest(BaseModel):
    """Used by /auth/register-admin — an ADMIN caller can grant any role,
    including ADMIN, unlike the public RegisterRequest above."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool
