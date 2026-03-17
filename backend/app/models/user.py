from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")

    # Relationships
    photos: Mapped[list["Photo"]] = relationship(back_populates="user", lazy="noload")  # noqa: F821
    people: Mapped[list["Person"]] = relationship(back_populates="user", lazy="noload")  # noqa: F821
    albums: Mapped[list["Album"]] = relationship(back_populates="user", lazy="noload")  # noqa: F821
