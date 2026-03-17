import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Person(Base, UUIDMixin, TimestampMixin):
    """A named cluster of face embeddings representing a single person."""

    __tablename__ = "people"

    name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    face_count: Mapped[int] = mapped_column(Integer, default=0)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="people")  # noqa: F821
    faces: Mapped[list["Face"]] = relationship(  # noqa: F821
        back_populates="person",
        foreign_keys="Face.person_id",
        cascade="all, delete-orphan",
    )
