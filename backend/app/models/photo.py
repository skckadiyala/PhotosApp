import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Photo(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "photos"

    file_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    # EXIF
    taken_at: Mapped[datetime | None] = mapped_column(index=True)
    camera_make: Mapped[str | None] = mapped_column(String(100))
    camera_model: Mapped[str | None] = mapped_column(String(100))
    lens_model: Mapped[str | None] = mapped_column(String(100))
    f_number: Mapped[float | None] = mapped_column(Float)
    exposure_time: Mapped[str | None] = mapped_column(String(20))
    iso: Mapped[int | None] = mapped_column(Integer)
    focal_length: Mapped[float | None] = mapped_column(Float)
    orientation: Mapped[int | None] = mapped_column(SmallInteger)

    # GPS (stored directly — no separate location table for Phase 1)
    gps_latitude: Mapped[float | None] = mapped_column(Float)
    gps_longitude: Mapped[float | None] = mapped_column(Float)

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Flags
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Thumbnail paths (relative to thumbnails_dir)
    thumb_sm: Mapped[str | None] = mapped_column(String(500))
    thumb_md: Mapped[str | None] = mapped_column(String(500))
    thumb_lg: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="photos")  # noqa: F821
    faces: Mapped[list["Face"]] = relationship(back_populates="photo", cascade="all, delete-orphan")  # noqa: F821
    location: Mapped["Location | None"] = relationship(back_populates="photos")  # noqa: F821
    tags: Mapped[list["PhotoTag"]] = relationship(back_populates="photo", cascade="save-update, merge")  # noqa: F821

    __table_args__ = (
        Index("idx_photos_user_taken", "user_id", "taken_at"),
        Index("idx_photos_not_processed", "is_processed", postgresql_where=(is_processed.is_(False))),
    )
