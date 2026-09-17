from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    module_code: Mapped[Optional[str]] = mapped_column(String(50))
    module_spec: Mapped[Optional[str]] = mapped_column(Text)  # Bounds what content is in scope

    # Relationships
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
