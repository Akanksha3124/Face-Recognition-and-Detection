"""
Person schemas. PersonCreate/PersonUpdate intentionally never accept
`id`, `created_at`, `updated_at` from the client — those are always
server-controlled.
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PersonBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    alternate_names: list[str] | None = None
    age: int | None = Field(default=None, ge=0, le=150)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    physical_description: str | None = None
    contact_info: str | None = Field(default=None, max_length=255)


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    """All fields optional — only what's set is changed (PATCH semantics,
    handled via `exclude_unset` in the route)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    alternate_names: list[str] | None = None
    age: int | None = Field(default=None, ge=0, le=150)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    physical_description: str | None = None
    contact_info: str | None = Field(default=None, max_length=255)


class PersonOut(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PaginatedPersons(BaseModel):
    items: list[PersonOut]
    total: int
    page: int
    page_size: int
