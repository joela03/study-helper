from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import ForeignKey, Text, Float, Integer, Date, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import SubjectProfile


class CardType(str, enum.Enum):
    FLASHCARD = "flashcard"
    PRACTICE_QUESTION = "practice_question"


class Card(Base, TimestampMixin):
    """
    Flashcard or practice question with SM-2 spaced repetition state.
    """
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))
    transcript_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transcripts.id"))

    card_type: Mapped[CardType] = mapped_column(Enum(CardType), default=CardType.FLASHCARD)

    # Content
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # SM-2 algorithm state
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)  # EF starts at 2.5
    interval: Mapped[int] = mapped_column(Integer, default=0)  # Days until next review
    repetitions: Mapped[int] = mapped_column(Integer, default=0)  # Successful reviews in a row
    next_review: Mapped[date] = mapped_column(Date, default=date.today)

    # Relationships
    profile: Mapped["SubjectProfile"] = relationship("SubjectProfile", back_populates="cards")

    def __repr__(self) -> str:
        return f"<Card {self.id} ({self.card_type.value})>"

    def update_sm2(self, quality: int) -> None:
        """
        Update card state using SM-2 algorithm.
        Quality: 0-5 (0-2 = fail, 3-5 = pass with varying ease)
        """
        if quality < 0 or quality > 5:
            raise ValueError("Quality must be between 0 and 5")

        if quality >= 3:
            # Successful review
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = round(self.interval * self.ease_factor)
            self.repetitions += 1
        else:
            # Failed review - reset
            self.repetitions = 0
            self.interval = 1

        # Update ease factor (minimum 1.3)
        self.ease_factor = max(
            1.3,
            self.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        )

        # Set next review date
        self.next_review = date.today() + timedelta(days=self.interval)
