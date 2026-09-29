from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person


async def create_person(db: AsyncSession, **fields) -> Person:
    person = Person(**fields)
    db.add(person)
    await db.flush()
    return person


async def get_person_by_id(db: AsyncSession, person_id: int) -> Person | None:
    return await db.get(Person, person_id)


async def list_persons(
    db: AsyncSession,
    *,
    name: str | None,
    gender: str | None,
    age_min: int | None,
    age_max: int | None,
    page: int,
    page_size: int,
) -> tuple[list[Person], int]:
    conditions = []
    if name:
        conditions.append(Person.name.ilike(f"%{name}%"))
    if gender:
        conditions.append(Person.gender == gender)
    if age_min is not None:
        conditions.append(Person.age >= age_min)
    if age_max is not None:
        conditions.append(Person.age <= age_max)

    count_stmt = select(func.count()).select_from(Person)
    stmt = select(Person)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        stmt = stmt.where(condition)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Person.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def update_person(db: AsyncSession, person: Person, changes: dict) -> Person:
    for key, value in changes.items():
        setattr(person, key, value)
    await db.flush()
    # updated_at is set server-side (onupdate=func.now()) — after an
    # UPDATE, SQLAlchemy marks it "expired" rather than fetching the new
    # value back, so touching it later (e.g. from Pydantic's
    # model_validate) would trigger an implicit lazy-load, which fails
    # outside an async context (MissingGreenlet). Refresh explicitly here
    # instead.
    await db.refresh(person)
    return person


async def delete_person(db: AsyncSession, person: Person) -> None:
    await db.delete(person)
    await db.flush()
