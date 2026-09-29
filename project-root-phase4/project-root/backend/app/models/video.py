from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Video(Base, TimestampMixin):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True)

    frames: Mapped[list["VideoFrame"]] = relationship(back_populates="video", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Video id={self.id}>"


class VideoFrame(Base):
    __tablename__ = "video_frames"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False, index=True)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)

    video: Mapped["Video"] = relationship(back_populates="frames")
    face_embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="video_frame", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<VideoFrame video_id={self.video_id} frame={self.frame_number}>"
