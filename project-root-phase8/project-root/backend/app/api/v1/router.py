"""
Top-level v1 API router. Sub-routers are registered here as each
module is implemented. Routes stay thin and delegate to app/services/*.
"""
from fastapi import APIRouter

from app.api.v1 import auth, cases, persons, rbac_demo, search

api_router = APIRouter()


@api_router.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "version": "v1"}


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(rbac_demo.router, prefix="/rbac-demo", tags=["rbac-demo (Phase 3 verification only)"])
api_router.include_router(persons.router, prefix="/persons", tags=["persons"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(search.router, prefix="/search", tags=["search"])

# Future routers (uncomment as each phase lands):
# from app.api.v1 import users
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# from app.api.v1 import faces
# api_router.include_router(faces.router, prefix="/faces", tags=["faces"])
# from app.api.v1 import matches
# api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
# from app.api.v1 import verification
# api_router.include_router(verification.router, prefix="/verification", tags=["verification"])
# from app.api.v1 import videos
# api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
# from app.api.v1 import locations
# api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
# from app.api.v1 import admin
# api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
