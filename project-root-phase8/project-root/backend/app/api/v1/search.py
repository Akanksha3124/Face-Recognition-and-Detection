"""
Face similarity search route. Read-level access (same roles as
persons/cases) since a search result is fundamentally "show me
candidate people," not a mutation.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_roles
from app.models import User
from app.schemas.search import SearchCandidateOut, SearchRequest, SearchResponse
from app.services import face_search_service

router = APIRouter()

READ_ROLES = ("ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER")


@router.post("/faces", response_model=SearchResponse)
async def search_faces(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _actor: User = Depends(require_roles(*READ_ROLES)),
) -> SearchResponse:
    try:
        candidates = await face_search_service.search(
            db,
            query_embedding=payload.embedding,
            top_k=payload.top_k,
            min_similarity=payload.min_similarity,
            case_type=payload.case_type,
            case_status=payload.case_status,
        )
    except face_search_service.InvalidEmbeddingDimension as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    return SearchResponse(
        results=[
            SearchCandidateOut(
                face_embedding_id=c.face_embedding_id,
                photo_id=c.photo_id,
                person_id=c.person_id,
                person_name=c.person_name,
                case_id=c.case_id,
                case_type=c.case_type,
                case_status=c.case_status,
                similarity_score=c.similarity_score,
            )
            for c in candidates
        ]
    )
