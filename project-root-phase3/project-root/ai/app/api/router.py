"""
AI service internal API router.
Endpoints are added as each pipeline stage is implemented
(detect: Phase 6, embed: Phase 7, search: Phase 8, video/analyze: Phase 13).
This service has no public port — it's only reachable from the backend
over the internal Docker network.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "ai"}

# Future endpoints (uncomment as each phase lands):
# @router.post("/detect")
# @router.post("/embed")
# @router.post("/search")
# @router.post("/video/analyze")
