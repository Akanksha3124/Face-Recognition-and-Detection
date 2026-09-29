# Security

This doc tracks security-relevant design decisions as they land, not a
final audit. Full hardening is Phase 19; this captures what's already in
place from earlier phases plus what's deliberately deferred.

## Authentication (Phase 3)

- **Passwords:** hashed with bcrypt via passlib (`app/core/security.py`),
  never stored or logged in plaintext.
- **Tokens:** JWT, HS256, signed with `SECRET_KEY` (must be a real secret
  in any non-local environment — `.env.example` ships an obvious
  placeholder). Access tokens expire in 30 minutes; refresh tokens in 7
  days (both configurable via env vars).
- **Refresh token revocation:** refresh tokens are stored server-side by
  SHA-256 hash (never plaintext) in `refresh_tokens`, with a `revoked`
  flag. This is what makes logout and rotation possible — a bare JWT
  can't be invalidated before it expires. On every `/auth/refresh` call,
  the presented token is revoked and a new pair issued (rotation), so a
  stolen-and-replayed old token fails once the legitimate client has
  moved past it.
- **No username enumeration via login:** `/auth/login` returns the same
  401 for "no such user" and "wrong password."
- **Privilege escalation via registration is blocked at the schema
  level:** `RegisterRequest.role` is a 3-value enum with no ADMIN option,
  so a request trying to self-register as ADMIN fails Pydantic validation
  (422) before any business logic runs. Creating an ADMIN account
  requires either the seed script or an existing ADMIN.

## Authorization

- RBAC is enforced via a FastAPI dependency (`require_roles()` in
  `app/core/deps.py`) applied per-route, not by any implicit global rule —
  every protected endpoint must explicitly declare which roles can call it.
- Authorization checks the user's role **from the database on every
  request**, not from the JWT's `role` claim. This costs one extra query
  per request but means a role change or `is_active = false` takes effect
  immediately, not only once the access token expires.

## Known gaps (deferred to later phases, tracked here so they aren't lost)

- **Rate limiting** on `/auth/login` and `/auth/register` — not yet
  implemented. Without it, the API is vulnerable to credential-stuffing /
  brute-force attempts. Planned for Phase 19.
- **CORS** is currently permissive for local dev
  (`ALLOWED_ORIGINS=http://localhost:5173`) — needs tightening for any
  real deployment.
- **HTTPS** is not enforced anywhere in the current setup (local dev over
  HTTP). Nginx TLS termination is planned for Phase 19.
- **Secrets management:** `.env` is git-ignored and `.env.example` has
  placeholder values, but there's no secrets manager / vault integration —
  fine for a student project, worth flagging as a real-deployment gap.
- **Audit logging of auth events** (login, failed login, logout,
  role changes) — the `audit_logs` table exists (Phase 2) but auth routes
  don't write to it yet. Worth adding alongside Phase 4's audit logging
  for case/person mutations, rather than duplicating the wiring now.

## Biometric data handling (forward-looking, Phase 6+)

Not yet relevant — no face data is processed until Phase 6 — but noted
here for continuity: face embeddings are treated as sensitive biometric
data throughout the architecture (see `docs/architecture.md`), gated
behind the same RBAC built in this phase, and every AI-generated match is
non-authoritative until a human reviewer approves it (`verification_records`,
Phase 2 schema).
