"""
Facial embeddings, stored as pgvector vectors (512-d, matching
ArcFace's standard output). Every embedding comes from exactly one
source — a photo OR a video frame, never both, enforced by a check
constraint.
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

EMBEDDING_DIM = 512


class FaceEmbedding(Base, TimestampMixin):
    __tablename__ = "face_embeddings"
    __table_args__ = (
        CheckConstraint(
            "(photo_id IS NOT NULL AND video_frame_id IS NULL) OR "
            "(photo_id IS NULL AND video_frame_id IS NOT NULL)",
            name="ck_face_embeddings_single_source",
        ),
        # IVFFlat index for approximate cosine-similarity search.
        # `lists` is tuned once there's real data volume (Phase 8);
        # 100 is a reasonable default starting point for a small/medium gallery.
        # GOTCHA for Phase 8: IVFFlat is approximate — with few rows relative
        # to `lists`, the default `ivfflat.probes = 1` can miss real matches
        # entirely. Either raise `SET LOCAL ivfflat.probes` for small
        # galleries or fall back to an exact scan below some row-count
        # threshold (see tests/test_models_schema.py::test_vector_similarity_search).
        Index(
            "ix_face_embeddings_embedding_cosine",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    photo_id: Mapped[int | None] = mapped_column(ForeignKey("photos.id"), nullable=True, index=True)
    video_frame_id: Mapped[int | None] = mapped_column(
        ForeignKey("video_frames.id"), nullable=True, index=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    photo: Mapped["Photo"] = relationship(back_populates="face_embeddings")
    video_frame: Mapped["VideoFrame"] = relationship(back_populates="face_embeddings")

    def __repr__(self) -> str:
        return f"<FaceEmbedding id={self.id} model={self.model_version}>"
