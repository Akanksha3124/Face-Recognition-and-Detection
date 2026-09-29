"""
AI service entrypoint.
Internal-only service: no public port, reached by the backend over
the Docker network (see infrastructure/docker-compose.yml).
Phase 6: face detection (POST /detect) is live. Embedding/matching/
video endpoints land in later phases.
"""
from fastapi import FastAPI

from app.api.router import router

app = FastAPI(title="Face Recognition AI Service")

app.include_router(router)


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"service": "ai", "status": "running"}
