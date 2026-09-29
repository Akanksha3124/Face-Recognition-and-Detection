/**
 * Mirrors backend/app/schemas/auth.py — keep these in sync manually for
 * now. A generated client (e.g. from the OpenAPI schema) is a reasonable
 * upgrade later, but isn't worth the tooling overhead yet.
 */
export type Role = "ADMIN" | "INVESTIGATOR" | "DISASTER_RESPONDER" | "VERIFIER";

// Roles a person can self-register as. ADMIN is deliberately excluded —
// matches RegisterRequest.role on the backend (see schemas/auth.py).
export type PublicRole = Exclude<Role, "ADMIN">;

export interface User {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  role: PublicRole;
}
