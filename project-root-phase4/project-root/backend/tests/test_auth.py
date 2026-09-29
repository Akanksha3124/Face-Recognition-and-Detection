"""
Authentication and RBAC tests, run against a real Postgres database
(see conftest.py). Covers: registration (public + admin-gated),
login, protected routes, refresh-token rotation, logout/revocation,
and per-role authorization on every seeded role.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def register_and_login(client: AsyncClient, email: str, password: str, role: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "role": role}
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

async def test_register_public_role_succeeds(client: AsyncClient, roles):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "inv1@example.com", "password": "password123", "role": "INVESTIGATOR"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "inv1@example.com"
    assert body["role"] == "INVESTIGATOR"
    assert body["is_active"] is True


@pytest.mark.parametrize("role", ["INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"])
async def test_register_each_public_role(client: AsyncClient, roles, role):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": f"{role.lower()}@example.com", "password": "password123", "role": role},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == role


async def test_register_cannot_grant_admin_publicly(client: AsyncClient, roles):
    """ADMIN is not a valid value for the public RegisterRequest schema —
    this should fail Pydantic validation before it ever reaches the DB."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "wannabe-admin@example.com", "password": "password123", "role": "ADMIN"},
    )
    assert resp.status_code == 422


async def test_register_duplicate_email_conflicts(client: AsyncClient, roles):
    payload = {"email": "dup@example.com", "password": "password123", "role": "VERIFIER"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_register_password_too_short_rejected(client: AsyncClient, roles):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short", "role": "VERIFIER"},
    )
    assert resp.status_code == 422


async def test_register_admin_requires_admin_auth(client: AsyncClient, roles):
    """No token at all -> 401 before authorization is even considered."""
    resp = await client.post(
        "/api/v1/auth/register-admin",
        json={"email": "new-admin@example.com", "password": "password123", "role": "ADMIN"},
    )
    assert resp.status_code == 401


async def test_register_admin_rejects_non_admin_caller(client: AsyncClient, roles):
    tokens = await register_and_login(client, "regular-inv@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/auth/register-admin",
        json={"email": "sneaky-admin@example.com", "password": "password123", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 403


async def test_register_admin_succeeds_for_existing_admin(client: AsyncClient, admin_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-123"}
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/register-admin",
        json={"email": "second-admin@example.com", "password": "password123", "role": "ADMIN"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "ADMIN"


# ---------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------

async def test_login_success_returns_token_pair(client: AsyncClient, roles):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login-ok@example.com", "password": "password123", "role": "VERIFIER"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "login-ok@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_rejected(client: AsyncClient, roles):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "password123", "role": "VERIFIER"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "not-the-password"}
    )
    assert resp.status_code == 401


async def test_login_nonexistent_email_rejected(client: AsyncClient, roles):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# Protected routes (/auth/me)
# ---------------------------------------------------------------------

async def test_me_without_token_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_invalid_token_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


async def test_me_with_valid_token_returns_profile(client: AsyncClient, roles):
    tokens = await register_and_login(client, "me-check@example.com", "password123", "DISASTER_RESPONDER")
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me-check@example.com"
    assert body["role"] == "DISASTER_RESPONDER"


# ---------------------------------------------------------------------
# Refresh token rotation
# ---------------------------------------------------------------------

async def test_refresh_issues_new_token_pair(client: AsyncClient, roles):
    tokens = await register_and_login(client, "refresh1@example.com", "password123", "VERIFIER")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


async def test_refresh_old_token_cannot_be_reused(client: AsyncClient, roles):
    """Rotation: once a refresh token has been used, it's revoked —
    replaying it (e.g. after theft) must fail."""
    tokens = await register_and_login(client, "refresh2@example.com", "password123", "VERIFIER")
    first_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first_refresh.status_code == 200

    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401


async def test_refresh_with_garbage_token_rejected(client: AsyncClient):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401


async def test_refresh_with_access_token_rejected(client: AsyncClient, roles):
    """An access token is not a refresh token, even though both are
    valid JWTs signed with the same key — the `type` claim must match."""
    tokens = await register_and_login(client, "refresh3@example.com", "password123", "VERIFIER")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


# ---------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------

async def test_logout_revokes_refresh_token(client: AsyncClient, roles):
    tokens = await register_and_login(client, "logout1@example.com", "password123", "VERIFIER")
    logout_resp = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_resp.status_code == 204

    reuse_attempt = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse_attempt.status_code == 401


async def test_logout_with_already_invalid_token_is_a_noop(client: AsyncClient):
    """Logging out with garbage shouldn't 500 — nothing to revoke, so it succeeds quietly."""
    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": "garbage"})
    assert resp.status_code == 204


# ---------------------------------------------------------------------
# RBAC — every role, positive and negative cases
# ---------------------------------------------------------------------

ROLE_ENDPOINTS = {
    "ADMIN": "/api/v1/rbac-demo/admin-only",
    "INVESTIGATOR": "/api/v1/rbac-demo/investigator-only",
    "DISASTER_RESPONDER": "/api/v1/rbac-demo/disaster-responder-only",
    "VERIFIER": "/api/v1/rbac-demo/verifier-only",
}


@pytest.mark.parametrize("role,endpoint", list(ROLE_ENDPOINTS.items()))
async def test_role_can_access_its_own_endpoint(client: AsyncClient, roles, admin_user, role, endpoint):
    if role == "ADMIN":
        login_resp = await client.post(
            "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-123"}
        )
        access_token = login_resp.json()["access_token"]
    else:
        tokens = await register_and_login(client, f"{role.lower()}-pos@example.com", "password123", role)
        access_token = tokens["access_token"]

    resp = await client.get(endpoint, headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == role


@pytest.mark.parametrize("endpoint", list(ROLE_ENDPOINTS.values()))
async def test_role_endpoints_reject_unauthenticated(client: AsyncClient, endpoint):
    resp = await client.get(endpoint)
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "wrong_role,endpoint",
    [
        ("INVESTIGATOR", ROLE_ENDPOINTS["ADMIN"]),
        ("VERIFIER", ROLE_ENDPOINTS["INVESTIGATOR"]),
        ("DISASTER_RESPONDER", ROLE_ENDPOINTS["VERIFIER"]),
        ("INVESTIGATOR", ROLE_ENDPOINTS["DISASTER_RESPONDER"]),
    ],
)
async def test_role_cannot_access_other_roles_endpoint(client: AsyncClient, roles, wrong_role, endpoint):
    tokens = await register_and_login(client, f"{wrong_role.lower()}-neg@example.com", "password123", wrong_role)
    resp = await client.get(endpoint, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 403


async def test_any_authenticated_endpoint_allows_every_role(client: AsyncClient, roles, admin_user):
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-123"}
    )
    admin_token = login_resp.json()["access_token"]
    resp = await client.get(
        "/api/v1/rbac-demo/any-authenticated", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200

    for role in ["INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"]:
        tokens = await register_and_login(client, f"{role.lower()}-any@example.com", "password123", role)
        resp = await client.get(
            "/api/v1/rbac-demo/any-authenticated",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == role


# ---------------------------------------------------------------------
# Deactivated user
# ---------------------------------------------------------------------

async def test_deactivated_user_loses_access_immediately(client: AsyncClient, roles, session):
    tokens = await register_and_login(client, "deactivate-me@example.com", "password123", "VERIFIER")

    from sqlalchemy import select

    from app.models import User

    user = await session.scalar(select(User).where(User.email == "deactivate-me@example.com"))
    user.is_active = False
    await session.flush()

    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    # Access is revoked immediately (checked against the DB on every
    # request), not only once the ~30 min access token expires.
    assert resp.status_code == 401
