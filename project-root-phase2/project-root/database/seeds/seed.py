"""
Seed data for local development and demos.

Run with:
    cd backend && python -m database.seeds.seed
(from the repo root, with PYTHONPATH including backend/ — see README)

Creates the four roles from the spec plus one demo user per role and a
couple of sample persons/cases so the frontend has something to render
once Phase 4/5 land. Safe to re-run: it checks for existing rows before
inserting.
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
from app.models import Case, CaseType, Person, Role, User

ROLE_NAMES = ["ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER"]

# Placeholder bcrypt hash for "changeme123" — real hashing lands in Phase 3.
# Never use this seed password/hash in a real deployment.
PLACEHOLDER_PASSWORD_HASH = "$2b$12$placeholderplaceholderplaceholderplaceholderplaceh."


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
    for name in ROLE_NAMES:
        email = f"{name.lower()}@example.com"
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            users[name] = existing
            continue
        user = User(
            email=email,
            password_hash=PLACEHOLDER_PASSWORD_HASH,
            role_id=roles[name].id,
        )
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
    print("Seed data applied.")


if __name__ == "__main__":
    asyncio.run(main())
