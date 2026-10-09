from typing import TYPE_CHECKING, Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.transcript import Transcript
    from app.models.card import Card
    from app.models.sample_question import SampleQuestion


class SubjectProfile(Base, TimestampMixin):
    """
    One profile per module/subject.
    Contains module spec and links to transcripts, cards, and sample questions.
    """
    __tablename__ = "subject_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Ownership lives here; everything else hangs off a subject
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    module_code: Mapped[Optional[str]] = mapped_column(String(50))
    module_spec: Mapped[Optional[str]] = mapped_column(Text)  # Bounds what content is in scope

    # The extraction prompt for this subject, written from its course
    # materials rather than hardcoded, so a maths module and a discursive
    # one get genuinely different instructions.
    concept_prompt: Mapped[Optional[str]] = mapped_column(Text)
    # Fingerprint of the materials it was written from; a mismatch means stale
    prompt_materials_hash: Mapped[Optional[str]] = mapped_column(String(64))
    prompt_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Hand-edited prompts are never silently overwritten by a regeneration
    prompt_is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profiles")
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript", back_populates="profile", cascade="all, delete-orphan"
    )
    cards: Mapped[list["Card"]] = relationship(
        "Card", back_populates="profile", cascade="all, delete-orphan"
    )
    sample_questions: Mapped[list["SampleQuestion"]] = relationship(
        "SampleQuestion", back_populates="profile", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SubjectProfile {self.name}>"
