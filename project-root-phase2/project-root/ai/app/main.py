"""
AI service entrypoint.
Phase 1: skeleton only — app boots, health check works.
No model loading, no inference logic yet.
Internal-only service: no public port, reached by the backend over
the Docker network (see infrastructure/docker-compose.yml).
"""
from fastapi import FastAPI

from app.api.router import router

app = FastAPI(title="Face Recognition AI Service")

app.include_router(router)


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"service": "ai", "status": "running"}
