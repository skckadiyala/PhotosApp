import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Album(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "albums"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cover_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    is_smart: Mapped[bool] = mapped_column(Boolean, default=False)
    smart_rules: Mapped[dict | None] = mapped_column(JSONB)
    photo_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="albums")  # noqa: F821
    album_photos: Mapped[list["AlbumPhoto"]] = relationship(
        back_populates="album", cascade="all, delete-orphan"
    )


class AlbumPhoto(Base):
    __tablename__ = "album_photos"

    album_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    album: Mapped["Album"] = relationship(back_populates="album_photos")
