import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Face(Base, UUIDMixin, TimestampMixin):
    """A single detected face within a photo."""

    __tablename__ = "faces"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), index=True
    )

    # Bounding box (top, right, bottom, left — face_recognition convention)
    bbox_top: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_right: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_bottom: Mapped[int] = mapped_column(Integer, nullable=False)
    bbox_left: Mapped[int] = mapped_column(Integer, nullable=False)

    # 512-d face embedding from DeepFace/ArcFace
    embedding = mapped_column(Vector(512), nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Euclidean distance from face embedding to the cluster centroid.
    # Lower = more confident match.  Used to flag uncertain assignments.
    match_distance: Mapped[float] = mapped_column(Float, default=0.0)

    # Confirmation status: confirmed / pending / rejected
    # "pending" faces appear in the review queue for user confirmation.
    status: Mapped[str] = mapped_column(String(20), default="confirmed", server_default="confirmed")

    # Relationships
    photo: Mapped["Photo"] = relationship(back_populates="faces")  # noqa: F821
    person: Mapped["Person"] = relationship(  # noqa: F821
        back_populates="faces",
        foreign_keys=[person_id],
    )
