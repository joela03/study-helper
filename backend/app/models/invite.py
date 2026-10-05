from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class InviteCode(Base, TimestampMixin):
    """
    A code that lets someone register while sign-ups are otherwise closed.

    Supports more than one use so a single link can be handed to a group,
    and an optional expiry so a code stops working on its own.
    """
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[Optional[str]] = mapped_column(String(255))

    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped["User"] = relationship("User")

    def is_redeemable(self, now: datetime) -> bool:
        if not self.is_active or self.uses >= self.max_uses:
            return False
        if self.expires_at and self.expires_at <= now:
            return False
        return True

    def __repr__(self) -> str:
        return f"<InviteCode {self.code} {self.uses}/{self.max_uses}>"
