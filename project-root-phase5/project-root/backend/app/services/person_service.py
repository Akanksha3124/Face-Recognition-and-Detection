"""
Person business logic. Every mutation writes an audit_logs row —
that's the "auditable" half of "case statuses should be configurable
and auditable" from the architecture doc, applied to persons too since
they carry the same sensitive PII.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, User
from app.repositories.audit_log_repository import create_audit_log
from app.repositories.person_repository import (
    create_person as repo_create_person,
    delete_person as repo_delete_person,
    get_person_by_id,
    list_persons as repo_list_persons,
    update_person as repo_update_person,
)
from app.utils.serialization import to_jsonable


class PersonNotFound(Exception):
    pass


async def create_person(db: AsyncSession, actor: User, data: dict) -> Person:
    person = await repo_create_person(db, **data)
    await create_audit_log(
        db,
        user_id=actor.id,
        action="CREATE",
        entity_type="person",
        entity_id=person.id,
        extra_data={"name": person.name},
    )
    return person


async def get_person(db: AsyncSession, person_id: int) -> Person:
    person = await get_person_by_id(db, person_id)
    if person is None:
        raise PersonNotFound(person_id)
    return person


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
    return await repo_list_persons(
        db, name=name, gender=gender, age_min=age_min, age_max=age_max, page=page, page_size=page_size
    )


async def update_person(db: AsyncSession, actor: User, person_id: int, changes: dict) -> Person:
    person = await get_person(db, person_id)
    before = {key: getattr(person, key) for key in changes}
    person = await repo_update_person(db, person, changes)
    await create_audit_log(
        db,
        user_id=actor.id,
        action="UPDATE",
        entity_type="person",
        entity_id=person.id,
        extra_data={"before": to_jsonable(before), "after": to_jsonable(changes)},
    )
    return person


async def delete_person(db: AsyncSession, actor: User, person_id: int) -> None:
    person = await get_person(db, person_id)
    await create_audit_log(
        db,
        user_id=actor.id,
        action="DELETE",
        entity_type="person",
        entity_id=person.id,
        extra_data={"name": person.name},
    )
    await repo_delete_person(db, person)
