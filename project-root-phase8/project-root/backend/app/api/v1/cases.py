"""
Case management routes. Case creation is nested under a person
(POST /persons/{person_id}/cases, in persons.py) since a case can't
exist without one; everything else (list/get/update/delete) is
top-level here, matching how a caller would look up or act on a case
once they already have its id.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_roles
from app.models import CaseType, User
from app.schemas.case import CaseOut, CaseUpdate, PaginatedCases
from app.services import case_service

router = APIRouter()

WRITE_ROLES = ("ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER")
READ_ROLES = ("ADMIN", "INVESTIGATOR", "DISASTER_RESPONDER", "VERIFIER")


@router.get("", response_model=PaginatedCases)
async def list_cases(
    case_type: CaseType | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    person_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _actor: User = Depends(require_roles(*READ_ROLES)),
) -> PaginatedCases:
    items, total = await case_service.list_cases(
        db, case_type=case_type, status=status_filter, person_id=person_id, page=page, page_size=page_size
    )
    return PaginatedCases(
        items=[CaseOut.model_validate(c) for c in items], total=total, page=page, page_size=page_size
    )


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    _actor: User = Depends(require_roles(*READ_ROLES)),
) -> CaseOut:
    try:
        case = await case_service.get_case(db, case_id)
    except case_service.CaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return CaseOut.model_validate(case)


@router.patch("/{case_id}", response_model=CaseOut)
async def update_case(
    case_id: int,
    payload: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles(*WRITE_ROLES)),
) -> CaseOut:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields provided to update")
    try:
        case = await case_service.update_case(db, actor, case_id, changes)
    except case_service.CaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    await db.commit()
    return CaseOut.model_validate(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_roles("ADMIN")),
) -> None:
    try:
        await case_service.delete_case(db, actor, case_id)
    except case_service.CaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    await db.commit()
