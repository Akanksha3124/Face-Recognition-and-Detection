"""
Case schemas.

`status` is deliberately a free string, not a fixed enum — the Case
model's comment explains why (auditable + configurable without a
migration). `created_by` is never client-supplied; the route sets it
from the authenticated caller.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.case import CaseType


class CaseCreate(BaseModel):
    case_type: CaseType
    status: str = Field(default="OPEN", max_length=50)


class CaseUpdate(BaseModel):
    case_type: CaseType | None = None
    status: str | None = Field(default=None, max_length=50)


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    case_type: CaseType
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime


class PaginatedCases(BaseModel):
    items: list[CaseOut]
    total: int
    page: int
    page_size: int
