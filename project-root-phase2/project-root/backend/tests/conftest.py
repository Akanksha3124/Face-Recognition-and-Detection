"""
Shared pytest fixtures for database tests.

Tests run against a real Postgres database with PostGIS and pgvector
enabled (set TEST_DATABASE_URL, or it defaults to a local Postgres on
localhost matching docker-compose's settings). Each test gets its own
engine + a transaction that's rolled back afterward, so tests never
leak state into each other. A fresh engine per test (rather than one
shared across the session) avoids asyncpg connections being reused
across the different event loops pytest-asyncio creates per test.
"""
import os

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/person_id_platform_test",
)


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
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
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
