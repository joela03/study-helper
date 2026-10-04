from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import SubjectProfile


class User(Base, TimestampMixin):
    """
    An account. Subjects belong to a user, and everything else — transcripts,
    cards, concepts, materials — hangs off a subject, so ownership is checked
    in one place.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Admins can read and manage other users' subjects
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profiles: Mapped[list["SubjectProfile"]] = relationship(
        "SubjectProfile", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}{' (admin)' if self.is_admin else ''}>"
