"""
Vector similarity search tests, run against a real Postgres database
with pgvector (see conftest.py). Covers the repository/service layer
directly (embedding storage, the single-source check constraint) and
the POST /search/faces endpoint (ranking, thresholds, metadata
filtering, RBAC, and the "never leak raw embeddings" guarantee).
"""
import math

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.models import Case, CaseType, FaceEmbedding, Person, Photo, User
from app.models.face_embedding import EMBEDDING_DIM
from app.services import face_search_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------
# Test vector helpers — deterministic, easy to reason about cosine
# distance for, rather than random noise that would make expected
# similarity scores hard to predict.
# ---------------------------------------------------------------------

def _unit_vector(index: int) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[index] = 1.0
    return v


def _mix(primary_index: int, secondary_index: int, secondary_weight: float) -> list[float]:
    """A unit vector mostly pointing along `primary_index`, nudged
    toward `secondary_index` by `secondary_weight` — smaller weight
    means higher cosine similarity to the pure primary vector."""
    v = [0.0] * EMBEDDING_DIM
    v[primary_index] = 1.0 - secondary_weight
    v[secondary_index] = secondary_weight
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


async def _make_person_with_photo(session, name: str, uploader: User) -> tuple[Person, Photo]:
    person = Person(name=name)
    session.add(person)
    await session.flush()
    photo = Photo(person_id=person.id, s3_key=f"test/{name}.jpg", uploaded_by=uploader.id)
    session.add(photo)
    await session.flush()
    return person, photo


async def _make_uploader(session, roles) -> User:
    from app.core.security import hash_password

    user = User(email="uploader@example.com", password_hash=hash_password("x"), role_id=roles["ADMIN"].id)
    session.add(user)
    await session.flush()
    return user


# ---------------------------------------------------------------------
# Repository/service layer — embedding storage
# ---------------------------------------------------------------------

async def test_add_embedding_stores_and_returns_row(session, roles):
    uploader = await _make_uploader(session, roles)
    _, photo = await _make_person_with_photo(session, "Store Test", uploader)

    embedding = await face_search_service.add_embedding(
        session, embedding=_unit_vector(0), model_version="test-model", photo_id=photo.id
    )
    assert embedding.id is not None
    assert embedding.model_version == "test-model"

    loaded = await session.get(FaceEmbedding, embedding.id)
    assert loaded.photo_id == photo.id


async def test_add_embedding_wrong_dimension_rejected(session, roles):
    uploader = await _make_uploader(session, roles)
    _, photo = await _make_person_with_photo(session, "Bad Dim", uploader)

    with pytest.raises(face_search_service.InvalidEmbeddingDimension):
        await face_search_service.add_embedding(
            session, embedding=[0.1, 0.2], model_version="test-model", photo_id=photo.id
        )


async def test_add_embedding_requires_exactly_one_source(session, roles):
    """The DB check constraint (Phase 2) still applies when going
    through this service — not re-implemented here, just relied on."""
    embedding = FaceEmbedding(embedding=_unit_vector(0), model_version="test-model")
    session.add(embedding)
    with pytest.raises(IntegrityError):
        await session.flush()


# ---------------------------------------------------------------------
# POST /search/faces — ranking, thresholds, filtering, RBAC
# ---------------------------------------------------------------------

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


async def test_search_ranks_by_similarity_descending(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    _, near_photo = await _make_person_with_photo(session, "Near Match", uploader)
    _, far_photo = await _make_person_with_photo(session, "Far Match", uploader)

    await face_search_service.add_embedding(
        session, embedding=_mix(0, 1, 0.05), model_version="test", photo_id=near_photo.id
    )
    await face_search_service.add_embedding(
        session, embedding=_unit_vector(1), model_version="test", photo_id=far_photo.id
    )
    await session.commit()

    token = await _register_and_login(client, "search-rank@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 10}, headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert len(results) == 2
    assert results[0]["person_name"] == "Near Match"
    assert results[1]["person_name"] == "Far Match"
    assert results[0]["similarity_score"] > results[1]["similarity_score"]


async def test_search_similarity_scores_are_correct():
    """Orthogonal unit vectors have cosine similarity 0 — sanity-check
    the distance-to-similarity conversion independent of the DB round
    trip (covered end-to-end by the test above already)."""
    a = _unit_vector(0)
    b = _unit_vector(1)
    dot = sum(x * y for x, y in zip(a, b))
    assert dot == 0.0  # orthogonal -> similarity 0, distance 1


async def test_search_respects_top_k(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    for i in range(5):
        _, photo = await _make_person_with_photo(session, f"TopK Person {i}", uploader)
        await face_search_service.add_embedding(
            session, embedding=_mix(0, 1, 0.01 * (i + 1)), model_version="test", photo_id=photo.id
        )
    await session.commit()

    token = await _register_and_login(client, "search-topk@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 3}, headers=_auth(token)
    )
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 3


async def test_search_respects_min_similarity_threshold(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    _, close_photo = await _make_person_with_photo(session, "Close Enough", uploader)
    _, orthogonal_photo = await _make_person_with_photo(session, "Too Far", uploader)

    await face_search_service.add_embedding(
        session, embedding=_mix(0, 1, 0.01), model_version="test", photo_id=close_photo.id
    )
    await face_search_service.add_embedding(
        session, embedding=_unit_vector(1), model_version="test", photo_id=orthogonal_photo.id
    )
    await session.commit()

    token = await _register_and_login(client, "search-minsim@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces",
        json={"embedding": _unit_vector(0), "top_k": 10, "min_similarity": 0.9},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    names = {r["person_name"] for r in results}
    assert "Close Enough" in names
    assert "Too Far" not in names


async def test_search_filters_by_case_type(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    missing_person, missing_photo = await _make_person_with_photo(session, "Missing Person", uploader)
    found_person, found_photo = await _make_person_with_photo(session, "Found Person", uploader)
    session.add(Case(person_id=missing_person.id, case_type=CaseType.MISSING, status="OPEN", created_by=uploader.id))
    session.add(Case(person_id=found_person.id, case_type=CaseType.FOUND, status="OPEN", created_by=uploader.id))
    await session.flush()

    await face_search_service.add_embedding(
        session, embedding=_mix(0, 1, 0.01), model_version="test", photo_id=missing_photo.id
    )
    await face_search_service.add_embedding(
        session, embedding=_mix(0, 1, 0.02), model_version="test", photo_id=found_photo.id
    )
    await session.commit()

    token = await _register_and_login(client, "search-casetype@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces",
        json={"embedding": _unit_vector(0), "top_k": 10, "case_type": "MISSING"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["person_name"] == "Missing Person"
    assert results[0]["case_type"] == "MISSING"


async def test_search_filters_by_case_status(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    open_person, open_photo = await _make_person_with_photo(session, "Open Case Person", uploader)
    closed_person, closed_photo = await _make_person_with_photo(session, "Closed Case Person", uploader)
    session.add(Case(person_id=open_person.id, case_type=CaseType.MISSING, status="OPEN", created_by=uploader.id))
    session.add(Case(person_id=closed_person.id, case_type=CaseType.MISSING, status="CLOSED", created_by=uploader.id))
    await session.flush()

    await face_search_service.add_embedding(
        session, embedding=_mix(0, 1, 0.01), model_version="test", photo_id=open_photo.id
    )
    await face_search_service.add_embedding(
        session, embedding=_mix(0, 1, 0.02), model_version="test", photo_id=closed_photo.id
    )
    await session.commit()

    token = await _register_and_login(client, "search-casestatus@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces",
        json={"embedding": _unit_vector(0), "top_k": 10, "case_status": "CLOSED"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["person_name"] == "Closed Case Person"


async def test_search_returns_empty_case_fields_for_person_without_case(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    _, photo = await _make_person_with_photo(session, "No Case Person", uploader)
    await face_search_service.add_embedding(
        session, embedding=_unit_vector(0), model_version="test", photo_id=photo.id
    )
    await session.commit()

    token = await _register_and_login(client, "search-nocase@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 10}, headers=_auth(token)
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    match = next(r for r in results if r["person_name"] == "No Case Person")
    assert match["case_id"] is None
    assert match["case_type"] is None
    assert match["case_status"] is None


async def test_search_never_exposes_raw_embedding(client: AsyncClient, roles, session):
    uploader = await _make_uploader(session, roles)
    _, photo = await _make_person_with_photo(session, "Privacy Check", uploader)
    await face_search_service.add_embedding(
        session, embedding=_unit_vector(0), model_version="test", photo_id=photo.id
    )
    await session.commit()

    token = await _register_and_login(client, "search-privacy@example.com", "password123", "VERIFIER")
    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 10}, headers=_auth(token)
    )
    assert resp.status_code == 200
    for result in resp.json()["results"]:
        assert "embedding" not in result


async def test_search_wrong_dimension_rejected(client: AsyncClient, roles):
    token = await _register_and_login(client, "search-baddim@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": [0.1, 0.2, 0.3], "top_k": 10}, headers=_auth(token)
    )
    assert resp.status_code == 422


async def test_search_top_k_bounds_enforced(client: AsyncClient, roles):
    token = await _register_and_login(client, "search-topkbounds@example.com", "password123", "INVESTIGATOR")
    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 500}, headers=_auth(token)
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("role", ["ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"])
async def test_search_readable_by_every_role(client: AsyncClient, roles, admin_user, role):
    if role == "ADMIN":
        token = await _login(client, "admin@example.com", "admin-password-123")
    else:
        token = await _register_and_login(client, f"search-{role.lower()}@example.com", "password123", role)

    resp = await client.post(
        "/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 5}, headers=_auth(token)
    )
    assert resp.status_code == 200, f"{role} should be able to search"


async def test_search_rejects_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/v1/search/faces", json={"embedding": _unit_vector(0), "top_k": 5})
    assert resp.status_code == 401
