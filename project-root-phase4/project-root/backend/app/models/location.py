"""
Locations with a PostGIS point geometry. location_type distinguishes
last-known / found / disaster / hospital / relief-camp points, per
the map module in the architecture doc. A spatial (GiST) index is
created automatically by geoalchemy2 via spatial_index=True.
"""
import enum

from geoalchemy2 import Geometry
from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LocationType(str, enum.Enum):
    LAST_KNOWN = "LAST_KNOWN"
    FOUND = "FOUND"
    DISASTER = "DISASTER"
    HOSPITAL = "HOSPITAL"
    RELIEF_CAMP = "RELIEF_CAMP"


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    geom: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="location_type"), nullable=False, index=True
    )
    address_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Location {self.location_type} id={self.id}>"
