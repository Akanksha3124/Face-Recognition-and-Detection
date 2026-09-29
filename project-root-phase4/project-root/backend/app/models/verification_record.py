"""
The human decision that closes a face_match. This table is what
enforces "no autonomous identification" at the data layer — a match
is never treated as confirmed anywhere in the system without a row
here naming the reviewer and their decision.
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class VerificationDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    face_match_id: Mapped[int] = mapped_column(
        ForeignKey("face_matches.id"), nullable=False, unique=True, index=True
    )
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    decision: Mapped[VerificationDecision] = mapped_column(
        Enum(VerificationDecision, name="verification_decision"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    face_match: Mapped["FaceMatch"] = relationship(back_populates="verification_record")
    reviewer: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<VerificationRecord match_id={self.face_match_id} decision={self.decision}>"
