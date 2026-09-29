# Database Schema

PostgreSQL 16 with two extensions: **PostGIS** (spatial data — `locations.geom`)
and **pgvector** (`face_embeddings.embedding`). Both are enabled by the first
migration, so a fresh database needs no manual setup beyond `alembic upgrade head`.

## Source of truth

The schema lives in `backend/app/models/*.py` (SQLAlchemy 2.0 declarative
models) and is applied via Alembic migrations in `backend/migrations/versions/`.
Never hand-edit the database directly — change a model, then generate a new
migration with `alembic revision --autogenerate -m "..."`.

## Tables

| Table | Purpose |
|---|---|
| `roles` | ADMIN / INVESTIGATOR / DISASTER_RESPONDER / VERIFIER — a table, not a hardcoded enum, so new roles don't need a migration |
| `users` | Login + role assignment |
| `persons` | The person being tracked across a case |
| `cases` | MISSING / FOUND / UNIDENTIFIED / PERSON_OF_INTEREST, linked to a person |
| `photos` | Uploaded images, stored in object storage (`s3_key` only lives here) |
| `videos` / `video_frames` | CCTV/video source material and its sampled frames |
| `face_embeddings` | 512-d pgvector embeddings, sourced from exactly one photo OR one video frame (enforced by a check constraint) |
| `face_matches` | AI-generated ranked candidates — always starts `PENDING`, never auto-approved |
| `verification_records` | The human decision that closes a `face_match` (one-to-one, enforced unique) |
| `locations` | PostGIS points for last-known/found/disaster/hospital/relief-camp locations |
| `audit_logs` | Append-only trail for every mutating action |
| `notifications` | Per-user notification feed |

## Key constraints

- `face_embeddings`: a check constraint requires exactly one of `photo_id` /
  `video_frame_id` to be set — an embedding always traces back to one real
  image.
- `verification_records.face_match_id` is unique — a match gets exactly one
  verification decision, not a history of overwritten ones (if a decision
  needs revisiting, that becomes a new match rather than mutating history).
- `face_matches.status` defaults to `PENDING` — nothing in the schema allows
  a match to become `APPROVED` without a row in `verification_records`
  pointing at a real reviewer.

## Indexes

- Standard btree indexes on all foreign keys and frequently-filtered columns
  (`cases.status`, `cases.case_type`, `persons.name`, etc.)
- `locations.geom`: GiST spatial index, created automatically by geoalchemy2
  when the table is created (not a separate `op.create_index` — see the
  comment in the initial migration if this trips you up again).
- `face_embeddings.embedding`: IVFFlat index with `vector_cosine_ops`,
  `lists=100`. **Known limitation, hit twice:** IVFFlat is approximate — on
  a small table (fewer rows than roughly `lists`), the default
  `ivfflat.probes = 1` can miss real matches. Phase 2's test hit this and
  raised probes to 10. Phase 8's search hit it *again* with probes at 10: the
  index is built once, at migration time, on an empty table, so its cluster
  centroids are effectively meaningless until it's rebuilt on real data —
  and probing 10% of meaningless clusters can still skip a real neighbor.
  **Current fix:** `IVFFLAT_PROBES = 100` in
  `backend/app/repositories/face_embedding_repository.py`, equal to `lists`,
  so every search probes every list — exhaustive, therefore exact, at any
  gallery size. This gives up IVFFlat's speed advantage entirely for now.
  **To revisit once there's real data:** rebuild the index after the gallery
  is populated (`REINDEX INDEX ix_face_embeddings_embedding_cosine`), then
  tune `probes` down and measure recall against an exact scan before trusting
  the approximate result. Covered by
  `backend/tests/test_face_search.py::test_search_ranks_by_similarity_descending`
  and `backend/tests/test_models_schema.py::test_vector_similarity_search`.

## Running migrations

```bash
cd backend
alembic upgrade head      # apply all migrations
alembic downgrade base    # revert to empty (tested — enum types are
                           # explicitly dropped in downgrade(), since
                           # Postgres ENUM types aren't cleaned up by
                           # dropping the tables that use them)
alembic revision --autogenerate -m "description"   # after changing a model
```

## Seed data

```bash
python -m database.seeds.seed   # run from repo root
```

Creates the four roles, one demo user per role (placeholder password hash —
real hashing lands in Phase 3), and one sample missing-person case. Safe to
re-run — it checks for existing rows before inserting.
