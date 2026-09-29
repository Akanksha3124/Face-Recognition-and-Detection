"""
Structural tests: every table, relationship, and constraint we defined
actually round-trips through SQLAlchemy against a real Postgres
instance with PostGIS + pgvector enabled.
"""
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models import (
    Case,
    CaseType,
    FaceEmbedding,
    FaceMatch,
    Location,
    LocationType,
    MatchStatus,
    Person,
    Photo,
    Role,
    User,
    VerificationDecision,
    VerificationRecord,
)

pytestmark = pytest.mark.asyncio


async def _make_role(session, name="ADMIN") -> Role:
    role = Role(name=name)
    session.add(role)
    await session.flush()
    return role


async def _make_user(session, role, email="user@example.com") -> User:
    user = User(email=email, password_hash="hashed", role_id=role.id)
    session.add(user)
    await session.flush()
    return user


async def test_create_role(session):
    role = await _make_role(session)
    assert role.id is not None
    assert role.name == "ADMIN"


async def test_role_name_unique(session):
    await _make_role(session, name="VERIFIER")
    session.add(Role(name="VERIFIER"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_create_user_with_role(session):
    role = await _make_role(session, name="INVESTIGATOR")
    user = await _make_user(session, role, email="inv@example.com")
    assert user.role_id == role.id
    loaded = await session.get(User, user.id)
    assert loaded.email == "inv@example.com"


async def test_user_email_unique(session):
    role = await _make_role(session, name="VERIFIER2")
    await _make_user(session, role, email="dup@example.com")
    session.add(User(email="dup@example.com", password_hash="x", role_id=role.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_person_with_alternate_names_array(session):
    person = Person(name="Jane Doe", alternate_names=["Jane D.", "J. Doe"], age=34)
    session.add(person)
    await session.flush()
    loaded = await session.get(Person, person.id)
    assert loaded.alternate_names == ["Jane D.", "J. Doe"]


async def test_case_requires_valid_person_fk(session):
    role = await _make_role(session, name="CASE_CREATOR")
    user = await _make_user(session, role, email="creator@example.com")
    session.add(Case(person_id=999999, case_type=CaseType.MISSING, status="OPEN", created_by=user.id))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_case_relationship_to_person(session):
    role = await _make_role(session, name="CASE_CREATOR2")
    user = await _make_user(session, role, email="creator2@example.com")
    person = Person(name="John Smith")
    session.add(person)
    await session.flush()

    case = Case(person_id=person.id, case_type=CaseType.UNIDENTIFIED, status="OPEN", created_by=user.id)
    session.add(case)
    await session.flush()

    result = await session.execute(select(Case).where(Case.person_id == person.id))
    cases = result.scalars().all()
    assert len(cases) == 1
    assert cases[0].case_type == CaseType.UNIDENTIFIED


async def test_location_point_geometry(session):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    point = from_shape(Point(73.8567, 18.5204), srid=4326)  # Pune, as an example coordinate
    location = Location(geom=point, location_type=LocationType.LAST_KNOWN, address_text="Pune, India")
    session.add(location)
    await session.flush()

    loaded = await session.get(Location, location.id)
    assert loaded.location_type == LocationType.LAST_KNOWN


async def test_face_embedding_requires_exactly_one_source(session):
    """CheckConstraint: photo_id XOR video_frame_id, never both, never neither."""
    session.add(FaceEmbedding(embedding=[0.1] * 512, model_version="arcface-v1"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_face_embedding_with_photo(session):
    role = await _make_role(session, name="UPLOADER")
    user = await _make_user(session, role, email="uploader@example.com")
    person = Person(name="Photo Person")
    session.add(person)
    await session.flush()

    photo = Photo(person_id=person.id, s3_key="photos/1.jpg", uploaded_by=user.id)
    session.add(photo)
    await session.flush()

    embedding = FaceEmbedding(photo_id=photo.id, embedding=[0.05] * 512, model_version="arcface-v1")
    session.add(embedding)
    await session.flush()

    loaded = await session.get(FaceEmbedding, embedding.id)
    assert len(loaded.embedding) == 512
    assert loaded.video_frame_id is None


async def test_face_match_defaults_to_pending_and_verification_flow(session):
    role = await _make_role(session, name="REVIEWER_ROLE")
    reviewer = await _make_user(session, role, email="reviewer@example.com")
    person = Person(name="Match Person")
    session.add(person)
    await session.flush()
    photo_a = Photo(person_id=person.id, s3_key="a.jpg", uploaded_by=reviewer.id)
    photo_b = Photo(person_id=person.id, s3_key="b.jpg", uploaded_by=reviewer.id)
    session.add_all([photo_a, photo_b])
    await session.flush()

    emb_a = FaceEmbedding(photo_id=photo_a.id, embedding=[0.1] * 512, model_version="arcface-v1")
    emb_b = FaceEmbedding(photo_id=photo_b.id, embedding=[0.2] * 512, model_version="arcface-v1")
    session.add_all([emb_a, emb_b])
    await session.flush()

    match = FaceMatch(query_embedding_id=emb_a.id, candidate_embedding_id=emb_b.id, similarity_score=0.87)
    session.add(match)
    await session.flush()
    assert match.status == MatchStatus.PENDING  # never auto-approved

    verification = VerificationRecord(
        face_match_id=match.id,
        reviewer_id=reviewer.id,
        decision=VerificationDecision.APPROVED,
        reason="Confirmed by reviewer in test.",
    )
    session.add(verification)
    await session.flush()

    # Query explicitly rather than touching the lazy relationship
    # attribute here — lazy-load IO isn't safe from a sync test body
    # even on an AsyncSession; the app's real async request handlers
    # use `selectinload`/`joinedload` for this instead.
    loaded_verification = await session.scalar(
        select(VerificationRecord).where(VerificationRecord.face_match_id == match.id)
    )
    assert loaded_verification is not None
    assert loaded_verification.decision == VerificationDecision.APPROVED


async def test_face_match_only_one_verification_record(session):
    """unique constraint on verification_records.face_match_id."""
    role = await _make_role(session, name="REVIEWER_ROLE2")
    reviewer = await _make_user(session, role, email="reviewer2@example.com")
    person = Person(name="Double Verify Person")
    session.add(person)
    await session.flush()
    photo = Photo(person_id=person.id, s3_key="c.jpg", uploaded_by=reviewer.id)
    session.add(photo)
    await session.flush()
    emb = FaceEmbedding(photo_id=photo.id, embedding=[0.3] * 512, model_version="arcface-v1")
    session.add(emb)
    await session.flush()
    match = FaceMatch(query_embedding_id=emb.id, candidate_embedding_id=emb.id, similarity_score=1.0)
    session.add(match)
    await session.flush()

    session.add(VerificationRecord(face_match_id=match.id, reviewer_id=reviewer.id, decision=VerificationDecision.APPROVED))
    await session.flush()

    session.add(VerificationRecord(face_match_id=match.id, reviewer_id=reviewer.id, decision=VerificationDecision.REJECTED))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_vector_similarity_search(session):
    """pgvector actually computes cosine distance, not just stores vectors."""
    person = Person(name="Vector Search Person")
    session.add(person)
    role = await _make_role(session, name="VEC_UPLOADER")
    user = await _make_user(session, role, email="vec@example.com")
    await session.flush()

    photo1 = Photo(person_id=person.id, s3_key="v1.jpg", uploaded_by=user.id)
    photo2 = Photo(person_id=person.id, s3_key="v2.jpg", uploaded_by=user.id)
    session.add_all([photo1, photo2])
    await session.flush()

    close_vector = [1.0] + [0.0] * 511
    far_vector = [0.0] * 511 + [1.0]
    query_vector = [0.99] + [0.01] * 511

    session.add_all([
        FaceEmbedding(photo_id=photo1.id, embedding=close_vector, model_version="arcface-v1"),
        FaceEmbedding(photo_id=photo2.id, embedding=far_vector, model_version="arcface-v1"),
    ])
    await session.flush()

    # IVFFlat is an approximate index: with only a couple of rows against
    # `lists=100`, the default probes=1 can miss matches entirely (a real
    # pgvector gotcha on small tables, not just a test artifact — the
    # AI service's search module will need to account for this too once
    # the gallery is small, e.g. by raising probes or using exact scan
    # below a row-count threshold). Raising probes here reflects that.
    await session.execute(text("SET LOCAL ivfflat.probes = 10"))
    result = await session.execute(
        select(FaceEmbedding)
        .order_by(FaceEmbedding.embedding.cosine_distance(query_vector))
        .limit(1)
    )
    nearest = result.scalar_one()
    assert nearest.photo_id == photo1.id  # the close vector should rank first
