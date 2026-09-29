"""
Password hashing and JWT helpers.
Placeholder interface only — implemented in Phase 3 (Authentication + RBAC).
"""


def hash_password(plain_password: str) -> str:
    raise NotImplementedError("Implemented in Phase 3")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    raise NotImplementedError("Implemented in Phase 3")


def create_access_token(subject: str) -> str:
    raise NotImplementedError("Implemented in Phase 3")


def create_refresh_token(subject: str) -> str:
    raise NotImplementedError("Implemented in Phase 3")
