import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Tag(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(50), index=True)  # object, scene, color, custom

    # Relationships
    photo_tags: Mapped[list["PhotoTag"]] = relationship(back_populates="tag", cascade="all, delete-orphan")


class PhotoTag(Base):
    __tablename__ = "photo_tags"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(20), default="ai")  # ai | manual

    # Relationships
    photo: Mapped["Photo"] = relationship(back_populates="tags")  # noqa: F821
    tag: Mapped["Tag"] = relationship(back_populates="photo_tags")
