"""
A face_match is a ranked candidate produced by the AI service — never
an automatic identification. status starts PENDING and is only moved
by a human reviewer via the verification workflow (verification_records).
"""
import enum

from sqlalchemy import Enum, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"


class FaceMatch(Base, TimestampMixin):
    __tablename__ = "face_matches"
    __table_args__ = (
        Index("ix_face_matches_query_status", "query_embedding_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    query_embedding_id: Mapped[int] = mapped_column(
        ForeignKey("face_embeddings.id"), nullable=False, index=True
    )
    candidate_embedding_id: Mapped[int] = mapped_column(
        ForeignKey("face_embeddings.id"), nullable=False, index=True
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status"), nullable=False, default=MatchStatus.PENDING, index=True
    )

    query_embedding: Mapped["FaceEmbedding"] = relationship(foreign_keys=[query_embedding_id])
    candidate_embedding: Mapped["FaceEmbedding"] = relationship(foreign_keys=[candidate_embedding_id])
    verification_record: Mapped["VerificationRecord"] = relationship(
        back_populates="face_match", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FaceMatch id={self.id} score={self.similarity_score} status={self.status}>"
