"""
Seed data for local development and demos.

Run with:
    cd backend && python -m database.seeds.seed
(from the repo root, with PYTHONPATH including backend/ — see README)

Creates the four roles from the spec plus one demo user per role and a
sample person/case so the frontend has something to render once Phase
4/5 land. Safe to re-run: it checks for existing rows before inserting.
"""
import asyncio
import sys
from pathlib import Path

# Allow running as `python -m database.seeds.seed` from repo root while
# importing the backend's `app` package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Case, CaseType, Person, Role, User

ROLE_NAMES = ["ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"]

# Every seeded demo user shares this password — local/demo use only.
# Never reuse this in a real deployment; real accounts go through
# /auth/register (public, non-admin roles) or /auth/register-admin
# (admin-only, any role) instead.
DEMO_PASSWORD = "changeme123"


async def seed_roles(session: AsyncSession) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name in ROLE_NAMES:
        existing = await session.scalar(select(Role).where(Role.name == name))
        if existing:
            roles[name] = existing
            continue
        role = Role(name=name)
        session.add(role)
        roles[name] = role
    await session.flush()
    return roles


async def seed_users(session: AsyncSession, roles: dict[str, Role]) -> dict[str, User]:
    users: dict[str, User] = {}
    password_hash = hash_password(DEMO_PASSWORD)
    for name in ROLE_NAMES:
        email = f"{name.lower()}@example.com"
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            users[name] = existing
            continue
        user = User(email=email, password_hash=password_hash, role_id=roles[name].id)
        session.add(user)
        users[name] = user
    await session.flush()
    return users


async def seed_persons_and_cases(session: AsyncSession, users: dict[str, User]) -> None:
    existing = await session.scalar(select(Person).where(Person.name == "Demo Missing Person"))
    if existing:
        return

    person = Person(
        name="Demo Missing Person",
        alternate_names=["Demo Alias"],
        age=29,
        gender="unspecified",
        physical_description="Seed data for local development — not a real case.",
    )
    session.add(person)
    await session.flush()

    case = Case(
        person_id=person.id,
        case_type=CaseType.MISSING,
        status="OPEN",
        created_by=users["INVESTIGATOR"].id,
    )
    session.add(case)


async def main() -> None:
    async with SessionLocal() as session:
        roles = await seed_roles(session)
        users = await seed_users(session, roles)
        await seed_persons_and_cases(session, users)
        await session.commit()
    print(f"Seed data applied. Demo login password for all seeded users: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
