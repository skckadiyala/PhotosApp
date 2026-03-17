from sqlalchemy import Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Location(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "locations"

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float | None] = mapped_column(Float)
    city: Mapped[str | None] = mapped_column(String(200), index=True)
    state: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100), index=True)
    formatted: Mapped[str | None] = mapped_column(Text)

    # Relationships
    photos: Mapped[list["Photo"]] = relationship(back_populates="location")  # noqa: F821

    __table_args__ = (
        Index("idx_locations_lat_lng", "latitude", "longitude"),
    )
