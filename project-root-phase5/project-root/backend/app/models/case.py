import enum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CaseType(str, enum.Enum):
    MISSING = "MISSING"
    FOUND = "FOUND"
    UNIDENTIFIED = "UNIDENTIFIED"
    PERSON_OF_INTEREST = "PERSON_OF_INTEREST"


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False, index=True)
    case_type: Mapped[CaseType] = mapped_column(Enum(CaseType, name="case_type"), nullable=False, index=True)
    # Free-form + auditable rather than a fixed enum: every change is
    # written to audit_logs by the service layer (Phase 4), so status
    # values can evolve without a migration.
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="OPEN", index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    person: Mapped["Person"] = relationship(back_populates="cases")

    def __repr__(self) -> str:
        return f"<Case {self.case_type} person_id={self.person_id}>"
