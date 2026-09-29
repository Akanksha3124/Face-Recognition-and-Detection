"""
Shared pytest fixtures for database and API tests.

Tests run against a real Postgres database with PostGIS and pgvector
enabled (set TEST_DATABASE_URL, or it defaults to a local Postgres on
localhost matching docker-compose's settings). Each test gets its own
engine + a transaction that's rolled back afterward, so tests never
leak state into each other. A fresh engine per test (rather than one
shared across the session) avoids asyncpg connections being reused
across the different event loops pytest-asyncio creates per test.

The `session` fixture uses join_transaction_mode="create_savepoint" so
that route handlers calling `await db.commit()` (the normal pattern —
see app/api/v1/auth.py) only commit a savepoint, not the outer test
transaction. Without this, an API test's first commit would end the
transaction the whole test relies on for isolation/rollback.
"""
import os

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.models import Base, Role, User

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/person_id_platform_test",
)

ROLE_NAMES = ["ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create extensions + all tables once before the test session, drop after."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    yield

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """
    A fresh engine + one rolled-back transaction per test — nothing
    written here persists, so tests can run in any order and be
    re-run freely.
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()

    yield session

    await session.close()
    # A test that asserts an IntegrityError already triggered an internal
    # rollback when the failed flush happened — guard against rolling
    # back an already-deassociated transaction in that case.
    if transaction.is_active:
        await transaction.rollback()
    await connection.close()
    await engine.dispose()


@pytest_asyncio.fixture
async def roles(session: AsyncSession) -> dict[str, Role]:
    """Seeds the four roles the app expects to already exist (normally
    done once via database/seeds/seed.py, not per-request)."""
    role_map: dict[str, Role] = {}
    for name in ROLE_NAMES:
        role = Role(name=name)
        session.add(role)
        role_map[name] = role
    await session.flush()
    return role_map


@pytest_asyncio.fixture
async def admin_user(session: AsyncSession, roles: dict[str, Role]) -> User:
    """
    Created directly against the DB, not through /auth/register-admin —
    that endpoint requires an already-authenticated ADMIN, so tests need
    at least one admin to exist before they can exercise it. This is the
    legitimate way to seed that first admin for a test, mirroring what
    database/seeds/seed.py does for local dev.
    """
    user = User(
        email="admin@example.com",
        password_hash=hash_password("admin-password-123"),
        role_id=roles["ADMIN"].id,
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    """
    An httpx AsyncClient wired to the real FastAPI app, with the
    get_db dependency overridden to hand out this test's transactional
    session — so requests made through `client` participate in the
    same rollback-at-teardown isolation as direct `session` usage.
    """
    from httpx import ASGITransport, AsyncClient

    from app.core.database import get_db
    from app.main import app

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
