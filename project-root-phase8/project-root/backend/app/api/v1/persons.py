"""
Person management routes. Read access is open to every role (a
VERIFIER needs to see who a case is about to verify a match sensibly);
writes are restricted to the roles that actually work cases day to
day. Deletion is ADMIN-only — removing a person record is destructive
and rare enough that it shouldn't be a routine INVESTIGATOR action.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_roles
from app.models import User
from app.schemas.case import CaseCreate, CaseOut
from app.schemas.person import PaginatedPersons, PersonCreate, PersonOut, PersonUpdate
from app.services import case_service, person_service

router = APIRouter()

WRITE_ROLES = ("ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER")
READ_ROLES = ("ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER")


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(
    payload: PersonCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*WRITE_ROLES)),
) -> PersonOut:
    person = await person_service.create_person(db, actor, payload.model_dump())
    await db.commit()
    return PersonOut.model_validate(person)


@router.get("", response_model=PaginatedPersons)
async def list_people(
    name: str | None = Query(default=None, description="Case-insensitive partial match"),
    gender: str | None = Query(default=None),
    age_min: int | None = Query(default=None, ge=0),
    age_max: int | None = Query(default=None, le=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _actor: User = Depends(require_roles(*READ_ROLES)),
) -> PaginatedPersons:
    items, total = await person_service.list_persons(
        db, name=name, gender=gender, age_min=age_min, age_max=age_max, page=page, page_size=page_size
    )
    return PaginatedPersons(
        items=[PersonOut.model_validate(p) for p in items], total=total, page=page, page_size=page_size
    )


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    _actor: User = Depends(require_roles(*READ_ROLES)),
) -> PersonOut:
    try:
        person = await person_service.get_person(db, person_id)
    except person_service.PersonNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    return PersonOut.model_validate(person)


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: int,
    payload: PersonUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*WRITE_ROLES)),
) -> PersonOut:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields provided to update")
    try:
        person = await person_service.update_person(db, actor, person_id, changes)
    except person_service.PersonNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    await db.commit()
    return PersonOut.model_validate(person)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(
    person_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles("ADMIN")),
) -> None:
    try:
        await person_service.delete_person(db, actor, person_id)
    except person_service.PersonNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    await db.commit()


@router.post("/{person_id}/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case_for_person(
    person_id: int,
    payload: CaseCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*WRITE_ROLES)),
) -> CaseOut:
    try:
        case = await case_service.create_case(db, actor, person_id, payload.model_dump())
    except person_service.PersonNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    await db.commit()
    return CaseOut.model_validate(case)
