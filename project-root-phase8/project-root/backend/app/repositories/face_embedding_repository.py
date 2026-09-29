"""
Storage and similarity search for facial embeddings.

Every search here raises `ivfflat.probes` before querying. Why: IVFFlat
is an approximate index — with few rows relative to the index's
`lists=100` (see the FaceEmbedding model), the default `probes=1` can
silently miss real nearest neighbors. This was a real bug caught during
Phase 2's own tests (see the comment on the model and
tests/test_models_schema.py::test_vector_similarity_search) — and it
resurfaced here even with probes raised to 10: on a near-empty table,
the index's cluster centroids (trained once, at index-creation time,
on whatever data existed then — effectively nothing) are close to
meaningless, so even probing 10% of lists can still skip a real match.
IVFFLAT_PROBES is set to 100 — equal to `lists`, i.e. every list is
probed, making the search exhaustive (and therefore exact) regardless
of gallery size. That trades away IVFFlat's speed advantage entirely
for now; tuning it back down is a real optimization to make once
there's enough data volume for approximate search to matter and enough
labeled data to verify the trade-off doesn't hurt recall (the same
Phase 11/12 evaluation work the quality thresholds elsewhere in this
project are deferred to).
"""
from sqlalchemy import Row, exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseType, FaceEmbedding, Person, Photo

IVFFLAT_PROBES = 100


async def create_embedding(
    db: AsyncSession,
    *,
    embedding: list[float],
    model_version: str,
    photo_id: int | None = None,
    video_frame_id: int | None = None,
) -> FaceEmbedding:
    """Exactly one of photo_id/video_frame_id must be set — enforced at
    the database level by a check constraint (app/models/face_embedding.py),
    not re-validated here, so a bad call fails loudly via IntegrityError
    rather than silently."""
    row = FaceEmbedding(
        photo_id=photo_id,
        video_frame_id=video_frame_id,
        embedding=embedding,
        model_version=model_version,
    )
    db.add(row)
    await db.flush()
    return row


async def search_similar(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int,
    min_similarity: float | None,
    case_type: CaseType | None,
    case_status: str | None,
) -> list[Row]:
    """
    Nearest-neighbor search over embeddings sourced from photos (video
    frame embeddings join through video_frames instead — not needed
    until the Phase 13 CCTV pipeline exists, so left for that phase to
    add rather than half-built here).

    Returns raw Row objects — (FaceEmbedding, Photo, Person, distance) —
    rather than a schema, so the service layer decides what a caller is
    allowed to see (in particular: never the raw embedding vector, and
    only a derived similarity score, not the internal distance metric).
    """
    await db.execute(text(f"SET LOCAL ivfflat.probes = {IVFFLAT_PROBES}"))

    distance = FaceEmbedding.embedding.cosine_distance(query_embedding)

    stmt = (
        select(FaceEmbedding, Photo, Person, distance.label("distance"))
        .join(Photo, FaceEmbedding.photo_id == Photo.id)
        .join(Person, Photo.person_id == Person.id)
    )

    if case_type is not None or case_status is not None:
        conditions = [Case.person_id == Person.id]
        if case_type is not None:
            conditions.append(Case.case_type == case_type)
        if case_status is not None:
            conditions.append(Case.status == case_status)
        stmt = stmt.where(exists().where(*conditions))

    if min_similarity is not None:
        # cosine_distance = 1 - cosine_similarity, so a similarity floor
        # becomes a distance ceiling.
        stmt = stmt.where(distance <= (1 - min_similarity))

    stmt = stmt.order_by(distance.asc()).limit(top_k)

    result = await db.execute(stmt)
    return list(result.all())


async def get_latest_case_by_person_id(db: AsyncSession, person_ids: list[int]) -> dict[int, Case]:
    """
    One case per person — whichever is most recently created — used to
    give search results case context without joining/duplicating rows
    per-case in the main search query (a person can have more than one
    case). Batched by person_id rather than queried per-candidate to
    avoid N+1 queries against a small, bounded result set (top_k rows).
    """
    if not person_ids:
        return {}
    stmt = (
        select(Case)
        .where(Case.person_id.in_(person_ids))
        .order_by(Case.person_id, Case.created_at.desc())
    )
    result = await db.execute(stmt)
    latest_by_person: dict[int, Case] = {}
    for case in result.scalars().all():
        latest_by_person.setdefault(case.person_id, case)
    return latest_by_person
