"""
Importing this package registers every model on Base.metadata, which
is what Alembic's autogenerate and create_all() rely on. Import order
doesn't matter for SQLAlchemy relationship resolution (it resolves
string references lazily), but every model must be imported somewhere
before metadata is used.
"""
from app.models.base import Base
from app.models.role import Role
from app.models.user import User
from app.models.location import Location, LocationType
from app.models.person import Person
from app.models.case import Case, CaseType
from app.models.photo import Photo
from app.models.video import Video, VideoFrame
from app.models.face_embedding import FaceEmbedding
from app.models.face_match import FaceMatch, MatchStatus
from app.models.verification_record import VerificationRecord, VerificationDecision
from app.models.audit_log import AuditLog
from app.models.notification import Notification

__all__ = [
    "Base",
    "Role",
    "User",
    "Location",
    "LocationType",
    "Person",
    "Case",
    "CaseType",
    "Photo",
    "Video",
    "VideoFrame",
    "FaceEmbedding",
    "FaceMatch",
    "MatchStatus",
    "VerificationRecord",
    "VerificationDecision",
    "AuditLog",
    "Notification",
]
