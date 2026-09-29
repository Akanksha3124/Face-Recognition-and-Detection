from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseType


async def create_case(db: AsyncSession, **fields) -> Case:
    case = Case(**fields)
    db.add(case)
    await db.flush()
    return case


async def get_case_by_id(db: AsyncSession, case_id: int) -> Case | None:
    return await db.get(Case, case_id)


async def list_cases(
    db: AsyncSession,
    *,
    case_type: CaseType | None,
    status: str | None,
    person_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[Case], int]:
    conditions = []
    if case_type is not None:
        conditions.append(Case.case_type == case_type)
    if status is not None:
        conditions.append(Case.status == status)
    if person_id is not None:
        conditions.append(Case.person_id == person_id)

    count_stmt = select(func.count()).select_from(Case)
    stmt = select(Case)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        stmt = stmt.where(condition)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Case.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def update_case(db: AsyncSession, case: Case, changes: dict) -> Case:
    for key, value in changes.items():
        setattr(case, key, value)
    await db.flush()
    # See the identical comment in person_repository.update_person —
    # updated_at is server-side (onupdate=func.now()) and needs an
    # explicit refresh after UPDATE to avoid an async lazy-load later.
    await db.refresh(case)
    return case


async def delete_case(db: AsyncSession, case: Case) -> None:
    await db.delete(case)
    await db.flush()
