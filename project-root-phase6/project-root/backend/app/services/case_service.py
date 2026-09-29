"""
Case business logic.

`status` is free-form for now (see the Case model's comment) — every
change is written to audit_logs, which is what keeps a free-form field
safe to use: nothing enforces which transitions are valid yet, but
every transition is fully traceable to who made it and when. A
dedicated "verified identification" transition, gated on an approved
verification_records row, arrives with the verification workflow
(Phase 15) — until then, any writer role can set any status string.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseType, User
from app.repositories.audit_log_repository import create_audit_log
from app.repositories.case_repository import (
    create_case as repo_create_case,
    delete_case as repo_delete_case,
    get_case_by_id,
    list_cases as repo_list_cases,
    update_case as repo_update_case,
)
from app.services.person_service import PersonNotFound, get_person
from app.utils.serialization import to_jsonable


class CaseNotFound(Exception):
    pass


async def create_case(db: AsyncSession, actor: User, person_id: int, data: dict) -> Case:
    await get_person(db, person_id)  # raises PersonNotFound if missing
    case = await repo_create_case(db, person_id=person_id, created_by=actor.id, **data)
    await create_audit_log(
        db,
        user_id=actor.id,
        action="CREATE",
        entity_type="case",
        entity_id=case.id,
        extra_data={"person_id": person_id, "case_type": case.case_type.value, "status": case.status},
    )
    return case


async def get_case(db: AsyncSession, case_id: int) -> Case:
    case = await get_case_by_id(db, case_id)
    if case is None:
        raise CaseNotFound(case_id)
    return case


async def list_cases(
    db: AsyncSession,
    *,
    case_type: CaseType | None,
    status: str | None,
    person_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[Case], int]:
    return await repo_list_cases(
        db, case_type=case_type, status=status, person_id=person_id, page=page, page_size=page_size
    )


async def update_case(db: AsyncSession, actor: User, case_id: int, changes: dict) -> Case:
    case = await get_case(db, case_id)
    before = {key: getattr(case, key) for key in changes}
    case = await repo_update_case(db, case, changes)
    await create_audit_log(
        db,
        user_id=actor.id,
        action="UPDATE",
        entity_type="case",
        entity_id=case.id,
        extra_data={"before": to_jsonable(before), "after": to_jsonable(changes)},
    )
    return case


async def delete_case(db: AsyncSession, actor: User, case_id: int) -> None:
    case = await get_case(db, case_id)
    await create_audit_log(
        db,
        user_id=actor.id,
        action="DELETE",
        entity_type="case",
        entity_id=case.id,
        extra_data={"person_id": case.person_id, "case_type": case.case_type.value},
    )
    await repo_delete_case(db, case)
