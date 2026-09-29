"""
Person/case management API tests, run against a real Postgres database
(see conftest.py). Covers CRUD, filtering/pagination, RBAC per role,
audit logging, and cross-entity behavior (creating a case for a
nonexistent person, etc.).
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditLog

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _register_and_login(client: AsyncClient, email: str, password: str, role: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "role": role}
    )
    assert resp.status_code == 201, resp.text
    return await _login(client, email, password)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# Person CRUD
# ---------------------------------------------------------------------

async def test_create_person_as_investigator(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-create@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/persons",
        json={"name": "Jane Doe", "age": 30, "gender": "female"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Jane Doe"
    assert body["age"] == 30
    assert "id" in body and "created_at" in body


async def test_create_person_requires_write_role(client: AsyncClient, roles):
    token = await _register_and_login(client, "verifier-create@example.com", "password123", "VERIFIER")
    resp = await client.post("/api/v1/persons", json={"name": "Blocked"}, headers=_auth(token))
    assert resp.status_code == 403


async def test_create_person_unauthenticated_rejected(client: AsyncClient):
    resp = await client.post("/api/v1/persons", json={"name": "Nobody"})
    assert resp.status_code == 401


async def test_create_person_validates_name_required(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-validate@example.com", "password123", "INVESTIGATOR")
    resp = await client.post("/api/v1/persons", json={"age": 30}, headers=_auth(token))
    assert resp.status_code == 422


async def test_get_person_by_id(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-get@example.com", "password123", "INVESTIGATOR")
    create_resp = await client.post("/api/v1/persons", json={"name": "Get Me"}, headers=_auth(token))
    person_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/persons/{person_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Me"


async def test_get_person_readable_by_every_role(client: AsyncClient, roles, admin_user):
    inv_token = await _register_and_login(client, "inv-owner@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Readable"}, headers=_auth(inv_token))
    ).json()["id"]

    for role in ["INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"]:
        token = await _register_and_login(client, f"{role.lower()}-reader@example.com", "password123", role)
        resp = await client.get(f"/api/v1/persons/{person_id}", headers=_auth(token))
        assert resp.status_code == 200, f"{role} should be able to read a person"

    admin_token = await _login(client, "admin@example.com", "admin-password-123")
    resp = await client.get(f"/api/v1/persons/{person_id}", headers=_auth(admin_token))
    assert resp.status_code == 200


async def test_get_nonexistent_person_404(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-404@example.com", "password123", "INVESTIGATOR")
    resp = await client.get("/api/v1/persons/999999", headers=_auth(token))
    assert resp.status_code == 404


async def test_update_person_partial_fields_only(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-update@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post(
            "/api/v1/persons", json={"name": "Original Name", "age": 25}, headers=_auth(token)
        )
    ).json()["id"]

    resp = await client.patch(f"/api/v1/persons/{person_id}", json={"age": 26}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["age"] == 26
    assert body["name"] == "Original Name"  # untouched


async def test_update_person_empty_body_rejected(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-empty-update@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Someone"}, headers=_auth(token))
    ).json()["id"]
    resp = await client.patch(f"/api/v1/persons/{person_id}", json={}, headers=_auth(token))
    assert resp.status_code == 400


async def test_update_person_requires_write_role(client: AsyncClient, roles):
    inv_token = await _register_and_login(client, "inv-for-update@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Protected"}, headers=_auth(inv_token))
    ).json()["id"]

    verifier_token = await _register_and_login(
        client, "verifier-blocked-update@example.com", "password123", "VERIFIER"
    )
    resp = await client.patch(
        f"/api/v1/persons/{person_id}", json={"age": 99}, headers=_auth(verifier_token)
    )
    assert resp.status_code == 403


async def test_delete_person_admin_only(client: AsyncClient, roles, admin_user):
    inv_token = await _register_and_login(client, "inv-for-delete@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Delete Target"}, headers=_auth(inv_token))
    ).json()["id"]

    # Investigator cannot delete, even though they can create/update.
    resp = await client.delete(f"/api/v1/persons/{person_id}", headers=_auth(inv_token))
    assert resp.status_code == 403

    admin_token = await _login(client, "admin@example.com", "admin-password-123")
    resp = await client.delete(f"/api/v1/persons/{person_id}", headers=_auth(admin_token))
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/persons/{person_id}", headers=_auth(admin_token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------
# Person listing / filtering / pagination
# ---------------------------------------------------------------------

async def test_list_persons_filters_by_name(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-list1@example.com", "password123", "INVESTIGATOR")
    await client.post("/api/v1/persons", json={"name": "Alice Wonderland"}, headers=_auth(token))
    await client.post("/api/v1/persons", json={"name": "Bob Builder"}, headers=_auth(token))

    resp = await client.get("/api/v1/persons", params={"name": "alice"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Alice Wonderland"


async def test_list_persons_filters_by_age_range(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-list2@example.com", "password123", "INVESTIGATOR")
    await client.post("/api/v1/persons", json={"name": "Young", "age": 10}, headers=_auth(token))
    await client.post("/api/v1/persons", json={"name": "Middle", "age": 40}, headers=_auth(token))
    await client.post("/api/v1/persons", json={"name": "Old", "age": 80}, headers=_auth(token))

    resp = await client.get(
        "/api/v1/persons", params={"age_min": 30, "age_max": 50}, headers=_auth(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Middle"


async def test_list_persons_pagination(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-list3@example.com", "password123", "INVESTIGATOR")
    for i in range(5):
        await client.post("/api/v1/persons", json={"name": f"Person {i}"}, headers=_auth(token))

    resp = await client.get("/api/v1/persons", params={"page": 1, "page_size": 2}, headers=_auth(token))
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


# ---------------------------------------------------------------------
# Case creation (nested under person) + validation
# ---------------------------------------------------------------------

async def test_create_case_for_person(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-case-create@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Case Subject"}, headers=_auth(token))
    ).json()["id"]

    resp = await client.post(
        f"/api/v1/persons/{person_id}/cases",
        json={"case_type": "MISSING"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["person_id"] == person_id
    assert body["case_type"] == "MISSING"
    assert body["status"] == "OPEN"  # schema default


async def test_create_case_for_nonexistent_person_404(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-case-404@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/persons/999999/cases", json={"case_type": "MISSING"}, headers=_auth(token)
    )
    assert resp.status_code == 404


async def test_create_case_invalid_case_type_rejected(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-case-badtype@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Bad Type Subject"}, headers=_auth(token))
    ).json()["id"]
    resp = await client.post(
        f"/api/v1/persons/{person_id}/cases", json={"case_type": "NOT_A_REAL_TYPE"}, headers=_auth(token)
    )
    assert resp.status_code == 422


async def test_create_case_requires_write_role(client: AsyncClient, roles):
    inv_token = await _register_and_login(client, "inv-case-owner@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "RBAC Subject"}, headers=_auth(inv_token))
    ).json()["id"]

    verifier_token = await _register_and_login(
        client, "verifier-case-blocked@example.com", "password123", "VERIFIER"
    )
    resp = await client.post(
        f"/api/v1/persons/{person_id}/cases", json={"case_type": "MISSING"}, headers=_auth(verifier_token)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------
# Case retrieval / update / delete / listing
# ---------------------------------------------------------------------

async def test_get_update_case(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-case-update@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Status Subject"}, headers=_auth(token))
    ).json()["id"]
    case_id = (
        await client.post(
            f"/api/v1/persons/{person_id}/cases", json={"case_type": "MISSING"}, headers=_auth(token)
        )
    ).json()["id"]

    get_resp = await client.get(f"/api/v1/cases/{case_id}", headers=_auth(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "OPEN"

    update_resp = await client.patch(
        f"/api/v1/cases/{case_id}", json={"status": "UNDER_REVIEW"}, headers=_auth(token)
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "UNDER_REVIEW"


async def test_case_status_change_is_audited(client: AsyncClient, roles, session):
    token = await _register_and_login(client, "inv-case-audit@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Audit Subject"}, headers=_auth(token))
    ).json()["id"]
    case_id = (
        await client.post(
            f"/api/v1/persons/{person_id}/cases", json={"case_type": "MISSING"}, headers=_auth(token)
        )
    ).json()["id"]

    await client.patch(f"/api/v1/cases/{case_id}", json={"status": "CLOSED"}, headers=_auth(token))

    result = await session.execute(
        select(AuditLog).where(AuditLog.entity_type == "case", AuditLog.entity_id == case_id)
    )
    logs = result.scalars().all()
    actions = {log.action for log in logs}
    assert "CREATE" in actions
    assert "UPDATE" in actions
    update_log = next(log for log in logs if log.action == "UPDATE")
    assert update_log.extra_data["after"]["status"] == "CLOSED"
    assert update_log.extra_data["before"]["status"] == "OPEN"


async def test_person_update_is_audited(client: AsyncClient, roles, session):
    token = await _register_and_login(client, "inv-person-audit@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Audited Person", "age": 20}, headers=_auth(token))
    ).json()["id"]
    await client.patch(f"/api/v1/persons/{person_id}", json={"age": 21}, headers=_auth(token))

    result = await session.execute(
        select(AuditLog).where(AuditLog.entity_type == "person", AuditLog.entity_id == person_id)
    )
    logs = result.scalars().all()
    actions = {log.action for log in logs}
    assert actions == {"CREATE", "UPDATE"}


async def test_delete_case_admin_only(client: AsyncClient, roles, admin_user):
    inv_token = await _register_and_login(client, "inv-case-delete@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Case Delete Subject"}, headers=_auth(inv_token))
    ).json()["id"]
    case_id = (
        await client.post(
            f"/api/v1/persons/{person_id}/cases", json={"case_type": "FOUND"}, headers=_auth(inv_token)
        )
    ).json()["id"]

    resp = await client.delete(f"/api/v1/cases/{case_id}", headers=_auth(inv_token))
    assert resp.status_code == 403

    admin_token = await _login(client, "admin@example.com", "admin-password-123")
    resp = await client.delete(f"/api/v1/cases/{case_id}", headers=_auth(admin_token))
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/cases/{case_id}", headers=_auth(admin_token))
    assert resp.status_code == 404


async def test_list_cases_filters_by_type_and_status(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-case-list@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Multi Case Subject"}, headers=_auth(token))
    ).json()["id"]
    await client.post(
        f"/api/v1/persons/{person_id}/cases", json={"case_type": "MISSING"}, headers=_auth(token)
    )
    found_case = (
        await client.post(
            f"/api/v1/persons/{person_id}/cases", json={"case_type": "FOUND"}, headers=_auth(token)
        )
    ).json()

    resp = await client.get("/api/v1/cases", params={"case_type": "FOUND"}, headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert all(item["case_type"] == "FOUND" for item in body["items"])
    assert any(item["id"] == found_case["id"] for item in body["items"])


async def test_list_cases_filters_by_person(client: AsyncClient, roles):
    token = await _register_and_login(client, "inv-case-byperson@example.com", "password123", "INVESTIGATOR")
    person_a = (
        await client.post("/api/v1/persons", json={"name": "Person A"}, headers=_auth(token))
    ).json()["id"]
    person_b = (
        await client.post("/api/v1/persons", json={"name": "Person B"}, headers=_auth(token))
    ).json()["id"]
    await client.post(f"/api/v1/persons/{person_a}/cases", json={"case_type": "MISSING"}, headers=_auth(token))
    await client.post(f"/api/v1/persons/{person_b}/cases", json={"case_type": "MISSING"}, headers=_auth(token))

    resp = await client.get("/api/v1/cases", params={"person_id": person_a}, headers=_auth(token))
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["person_id"] == person_a


async def test_case_endpoints_readable_by_verifier(client: AsyncClient, roles):
    inv_token = await _register_and_login(client, "inv-case-for-verifier@example.com", "password123", "INVESTIGATOR")
    person_id = (
        await client.post("/api/v1/persons", json={"name": "Verifier Read Subject"}, headers=_auth(inv_token))
    ).json()["id"]
    case_id = (
        await client.post(
            f"/api/v1/persons/{person_id}/cases", json={"case_type": "UNIDENTIFIED"}, headers=_auth(inv_token)
        )
    ).json()["id"]

    verifier_token = await _register_and_login(
        client, "verifier-case-reader@example.com", "password123", "VERIFIER"
    )
    resp = await client.get(f"/api/v1/cases/{case_id}", headers=_auth(verifier_token))
    assert resp.status_code == 200

    # But a verifier still can't write.
    resp = await client.patch(
        f"/api/v1/cases/{case_id}", json={"status": "CLOSED"}, headers=_auth(verifier_token)
    )
    assert resp.status_code == 403


async def test_case_and_person_endpoints_reject_unauthenticated(client: AsyncClient):
    assert (await client.get("/api/v1/persons")).status_code == 401
    assert (await client.get("/api/v1/cases")).status_code == 401
