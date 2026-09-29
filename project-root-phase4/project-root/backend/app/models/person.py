from datetime import date

from sqlalchemy import ARRAY, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alternate_names: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    physical_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_known_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )

    last_known_location: Mapped["Location"] = relationship()
    cases: Mapped[list["Case"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    photos: Mapped[list["Photo"]] = relationship(back_populates="person", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Person {self.name}>"
