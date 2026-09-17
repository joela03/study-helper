from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import ForeignKey, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import SubjectProfile


class QuestionSource(str, enum.Enum):
    WORKSHEET = "worksheet"  # Used as few-shot exemplars for generating new questions
    PAST_EXAM = "past_exam"  # Used for difficulty/coverage calibration


class SampleQuestion(Base, TimestampMixin):
    """
    Sample questions from worksheets or past exams.
    Used as references for generating new practice questions.
    """
    __tablename__ = "sample_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))

    source: Mapped[QuestionSource] = mapped_column(Enum(QuestionSource))
    source_name: Mapped[Optional[str]] = mapped_column(String(255))  # e.g., "Worksheet 3", "2023 Exam"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)  # May not have answers for all

    # Relationships
    profile: Mapped["SubjectProfile"] = relationship("SubjectProfile", back_populates="sample_questions")

    def __repr__(self) -> str:
        return f"<SampleQuestion {self.id} ({self.source.value})>"
