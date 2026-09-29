# AI-Based Face Recognition and Person Identification Platform

A decision-support platform for missing-person identification, disaster-victim
identification, and authorized person-of-interest matching. Face recognition
results are always **candidate leads, never automatic decisions** — every
match requires human verification before a case status changes.

> **Status: Phase 7 — face embedding service.** Backend (Phases 1–4) and
> frontend auth/dashboard (Phase 5) are in place. The AI service performs
> face detection (Phase 6) and now face embedding: `POST /embed` aligns a
> detected (or explicitly specified) face and generates a 512-d ArcFace
> embedding via a CPU-friendly ONNX model. No vector storage or similarity
> search yet — that starts Phase 8.

## Overview

The platform supports:
- Missing-person, disaster-victim, and unidentified-individual case management
- Face matching across age gaps and appearance changes (makeup, disguise, pose, lighting, occlusion)
- Authorized CCTV/footage search
- Human-in-the-loop verification with full audit logging
- Role-based access control (ADMIN, INVESTIGATOR, DISASTER_RESPONDER, VERIFIER)

See `docs/architecture.md` for the full system design (agreed before Phase 1
began) and the phase list below for build order.

## Architecture

```
React frontend  ─▶  FastAPI backend  ─▶  AI service (FastAPI + PyTorch)
                          │                     │
                     PostgreSQL            Model cache
                  (+ PostGIS, pgvector)    (loaded once)
                          │
                    MinIO / S3 (photos)
```

The frontend never talks to the AI service directly — everything routes
through the backend. Full details in `docs/architecture.md`.

## Tech Stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS, React Router, Axios, TanStack Query, Recharts, Leaflet/OpenStreetMap

**Backend:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, PostGIS, pgvector, JWT, bcrypt/Argon2

**AI:** Python, PyTorch, OpenCV, InsightFace/ArcFace, RetinaFace/MTCNN, ONNX Runtime, NumPy, FAISS/pgvector

**Storage:** MinIO (dev) / S3-compatible (prod)

**Infra:** Docker, Docker Compose, Nginx

**Testing:** Pytest, FastAPI TestClient, React Testing Library, Playwright

## Repository Structure

```
frontend/     React + TypeScript UI
backend/      FastAPI case-management API (routes → services → repositories)
ai/           Internal-only FastAPI face-recognition microservice
common/       Shared schemas between backend and ai
database/     Schema references, seeds, scripts
infrastructure/  Docker Compose, Nginx config
docs/         Architecture, API, database, AI pipeline, deployment, security, testing docs
tests/        Cross-service integration and e2e tests
```

## Installation

### Prerequisites
- Docker + Docker Compose
- Node.js 20+ (for local frontend dev outside Docker)
- Python 3.12+ (for local backend/ai dev outside Docker)

### Environment Variables

```bash
cp .env.example .env
# edit .env with real values — never commit .env
```

See `.env.example` for the full list (database URL, JWT secret, storage
credentials, AI service URL, CORS origins).

### Database Setup

Postgres runs via a small custom image (`infrastructure/docker/postgres/Dockerfile`)
built on `postgis/postgis:16-3.4` with `postgresql-16-pgvector` installed on
top — PostGIS and pgvector both need to live in the same instance, and no
single official image ships both.

Apply the schema with Alembic (the first migration also enables both
extensions, so a completely fresh database needs no manual setup):

```bash
cd backend
alembic upgrade head
```

Then seed demo data (roles, one user per role, a sample case):

```bash
cd ..            # repo root
python -m database.seeds.seed
```

Or do both at once locally with `database/scripts/reset_db.sh`. Full schema
documentation — tables, constraints, indexes, and a known pgvector gotcha
worth knowing before Phase 8 — is in `docs/database.md`.

### AI Model Setup

Phase 6 (detection) and Phase 7 (embedding) need models downloaded before
first run:

```bash
cd ai
python scripts/download_models.py
```

Downloads OpenCV's SSD ResNet-10 face detector (~10MB) and insightface's
`w600k_mbf.onnx` recognition model (~14MB, extracted from a larger pack —
see the script) into `ai/models/` — neither is committed to the repo. See
`docs/ai_pipeline.md` for why these specific models were chosen over the
RetinaFace/MTCNN + larger ArcFace variants named in the original
architecture, and the accuracy trade-offs that decision carries.

## Running Locally

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**AI service:**
```bash
cd ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Running with Docker

```bash
cd infrastructure
docker compose up --build
```

- Frontend: http://localhost:5173 (direct) or http://localhost:8080 (via nginx)
- Backend: http://localhost:8000
- AI service: http://localhost:8100 (internal-only in production topology)
- MinIO console: http://localhost:9001

## Person & Case Management

Full CRUD for persons and cases (`/api/v1/persons`, `/api/v1/cases`):

- **Read** (list, get, filter, paginate) is open to every role — a
  VERIFIER needs case context to verify a match sensibly.
- **Create/update** is restricted to `ADMIN`, `INVESTIGATOR`,
  `DISASTER_RESPONDER` — the roles that actually work cases day to day.
- **Delete** is `ADMIN`-only for both persons and cases — destructive and
  rare enough that it shouldn't be a routine action for other roles.
  Deleting a person cascades to their cases (`ON DELETE` via the ORM
  relationship, not a raw FK cascade — see `app/models/person.py`).
- **Every create/update/delete writes an `audit_logs` row** (who, when,
  before/after values for updates) — this is what makes the free-form
  `case.status` field (see `app/models/case.py`) safe to use without a
  fixed state machine: nothing enforces valid transitions yet, but every
  transition is fully traceable. A stricter "verified identification"
  transition gated on an approved verification record arrives with the
  verification workflow (Phase 15).
- A case can't exist without a person — case creation is nested under
  `POST /persons/{person_id}/cases` rather than being a bare top-level
  endpoint.

## Frontend Authentication & Dashboard (Phase 5)

- `/login`, `/register`, `/dashboard`, `/profile` are implemented and
  wired to the real backend — no mocked data.
- **Token handling:** access token lives in memory only; refresh token
  lives in `localStorage` so a page reload doesn't force a re-login. This
  is a deliberate trade-off (documented in `src/api/client.ts`) — an
  httpOnly cookie would be safer against XSS, but the backend currently
  returns both tokens in the JSON response body rather than setting a
  cookie. Revisit alongside Phase 19 security hardening if this becomes a
  real deployment rather than a student project.
- **Automatic refresh:** a 401 anywhere triggers exactly one silent
  refresh-and-retry; concurrent 401s share a single in-flight refresh
  call instead of racing. A refresh that fails (token itself expired or
  revoked) clears local state and redirects to `/login`.
- **Route guards:** `ProtectedRoute` redirects unauthenticated visitors to
  `/login` (remembering where they were headed); `PublicOnlyRoute` sends
  already-logged-in users away from `/login`/`/register` to `/dashboard`.
- The dashboard shows three real numbers (total persons, total cases,
  open cases) pulled from the Phase 4 API via TanStack Query — deliberately
  minimal. Charts, recent activity, and geographic distribution are
  Phase 16 (admin dashboard), not duplicated here.
- The sidebar nav includes links to `/persons`, `/cases`, `/face-search`,
  etc. that don't have pages behind them yet — those land with their
  respective phases (Phase 6+ for face features, Phase 16 for admin).

Run locally with the backend already running on `:8000`:
```bash
cd frontend
cp .env.example .env   # points at http://localhost:8000/api/v1
npm install
npm run dev
```

## Authentication & RBAC

JWT-based auth with four roles: `ADMIN`, `INVESTIGATOR`,
`DISASTER_RESPONDER`, `VERIFIER`. Key points (full detail in `docs/api.md`):

- Public registration (`POST /api/v1/auth/register`) can only create
  INVESTIGATOR / DISASTER_RESPONDER / VERIFIER accounts — never ADMIN.
  ADMIN accounts come from `database/seeds/seed.py` or from an existing
  ADMIN calling `POST /api/v1/auth/register-admin`.
- Access tokens are short-lived (30 min); refresh tokens are tracked
  server-side by hash and rotate on every use, so they can be revoked
  (logout) and a stolen-and-replayed old refresh token is rejected.
- Authorization (`require_roles()` in `app/core/deps.py`) checks the
  caller's role fresh from the database on every request — not from the
  JWT — so a role change or deactivation takes effect immediately.
- All seeded demo users (`database/seeds/seed.py`) share the password
  `changeme123`.

Test with the running server, e.g.:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme123"}'
```

## Testing

```bash
# Backend (real Postgres with PostGIS + pgvector required — see docs/database.md)
cd backend && pytest

# AI service
cd ai && pytest

# Frontend (added once test tooling is configured, Phase 17)
cd frontend && npm test
```

## API Documentation

Interactive OpenAPI docs are auto-generated by FastAPI at `/docs` on the
backend service once it's running. Endpoint-level design — including the
RBAC model and the reasoning behind key auth decisions — is in `docs/api.md`.

## Development Phases

1. Architecture + repository structure *(this phase)*
2. Database schema + migrations
3. Authentication + RBAC
4. Person/case management APIs
5. Frontend authentication + dashboard
6. Face detection service
7. Face embedding service
8. Vector similarity search
9. Face matching API
10. Frontend face-search interface
11. Age-gap experiments
12. Appearance/disguise robustness experiments
13. CCTV/video pipeline
14. Map/PostGIS integration
15. Verification workflow
16. Admin dashboard
17. Testing
18. Dockerization
19. Security hardening
20. Documentation

## Limitations

Documented in full in `docs/architecture.md` — summary: age-gap and
disguise/occlusion matching are open problems, not solved by pretrained
models out of the box; false positives are expected at gallery scale, which
is why human verification is mandatory rather than optional; face embeddings
are treated as sensitive biometric data throughout the system.
