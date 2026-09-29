"""
Face similarity search business logic.

This is the "Vector Similarity Search" mechanism itself (storage +
nearest-neighbor search with filtering and ranking) — not the full
upload-a-photo-and-get-matches pipeline. That pipeline needs the
backend to call the AI service's POST /embed (see ai/app/api/router.py,
Phase 7) and turn results into face_matches rows for human
verification; both are Phase 9's job ("Face matching API"). This phase
only builds the search capability Phase 9 will call.
"""
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseType, FaceEmbedding, Person, Photo
from app.models.face_embedding import EMBEDDING_DIM
from app.repositories.face_embedding_repository import (
    create_embedding,
    get_latest_case_by_person_id,
    search_similar,
)


class InvalidEmbeddingDimension(Exception):
    def __init__(self, actual: int):
        self.actual = actual
        super().__init__(f"Embedding must have exactly {EMBEDDING_DIM} dimensions, got {actual}")


@dataclass
class SearchCandidate:
    face_embedding_id: int
    photo_id: int
    person_id: int
    person_name: str
    case_id: int | None
    case_type: CaseType | None
    case_status: str | None
    similarity_score: float


async def add_embedding(
    db: AsyncSession,
    *,
    embedding: list[float],
    model_version: str,
    photo_id: int | None = None,
    video_frame_id: int | None = None,
) -> FaceEmbedding:
    if len(embedding) != EMBEDDING_DIM:
        raise InvalidEmbeddingDimension(len(embedding))
    return await create_embedding(
        db,
        embedding=embedding,
        model_version=model_version,
        photo_id=photo_id,
        video_frame_id=video_frame_id,
    )


async def search(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    top_k: int,
    min_similarity: float | None,
    case_type: CaseType | None,
    case_status: str | None,
) -> list[SearchCandidate]:
    if len(query_embedding) != EMBEDDING_DIM:
        raise InvalidEmbeddingDimension(len(query_embedding))

    rows = await search_similar(
        db,
        query_embedding=query_embedding,
        top_k=top_k,
        min_similarity=min_similarity,
        case_type=case_type,
        case_status=case_status,
    )

    person_ids = [person.id for _, _, person, _ in rows]
    latest_case_by_person = await get_latest_case_by_person_id(db, person_ids)

    candidates: list[SearchCandidate] = []
    for face_embedding, photo, person, distance in rows:
        case = latest_case_by_person.get(person.id)
        candidates.append(
            SearchCandidate(
                face_embedding_id=face_embedding.id,
                photo_id=photo.id,
                person_id=person.id,
                person_name=person.name,
                case_id=case.id if case else None,
                case_type=case.case_type if case else None,
                case_status=case.status if case else None,
                # cosine_distance = 1 - cosine_similarity (pgvector convention)
                similarity_score=1.0 - float(distance),
            )
        )
    return candidates
