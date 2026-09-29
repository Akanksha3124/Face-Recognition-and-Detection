"""
Roles table. Kept as a table (not a hardcoded enum) so new roles can be
added without a schema migration, per the "don't create unnecessary
roles" rule — the four seeded roles cover the spec, more can be added
via seed data later if the project genuinely needs them.
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
