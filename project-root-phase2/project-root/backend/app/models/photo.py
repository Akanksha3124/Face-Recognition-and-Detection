from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Photo(Base, TimestampMixin):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False, index=True)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    person: Mapped["Person"] = relationship(back_populates="photos")
    face_embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Photo id={self.id} person_id={self.person_id}>"
