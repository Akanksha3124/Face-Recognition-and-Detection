"""
Search request/response schemas.

SearchCandidateOut deliberately has no `embedding` field — "don't
expose raw embeddings to normal frontend users" from the architecture
doc. A similarity score is all a caller ever needs to rank or display
a candidate.

SearchRequest takes a precomputed embedding vector directly rather
than an image, because generating one is the AI service's job (Phase
7's POST /embed) — the backend hasn't been wired to call it yet
(that's Phase 9, "Face matching API"). This endpoint is the search
mechanism Phase 9 will call once that wiring exists.
"""
from pydantic import BaseModel, Field

from app.models.case import CaseType
from app.models.face_embedding import EMBEDDING_DIM


class SearchRequest(BaseModel):
    embedding: list[float] = Field(min_length=EMBEDDING_DIM, max_length=EMBEDDING_DIM)
    top_k: int = Field(default=10, ge=1, le=50)
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    case_type: CaseType | None = None
    case_status: str | None = Field(default=None, max_length=50)


class SearchCandidateOut(BaseModel):
    face_embedding_id: int
    photo_id: int
    person_id: int
    person_name: str
    case_id: int | None
    case_type: CaseType | None
    case_status: str | None
    similarity_score: float


class SearchResponse(BaseModel):
    results: list[SearchCandidateOut]
