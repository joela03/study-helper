from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import SubjectProfile
    from app.models.transcript import Transcript
    from app.models.card import Card


class Concept(Base, TimestampMixin):
    """
    One idea from a lecture, condensed into something you can hold in your
    head before trying to recall it.

    Sits above the flashcards: a concept explains, its cards test. Ordered by
    order_index so the set reads in teaching order.
    """
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"))

    # Position in the lecture, so the tabs read front to back
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    title: Mapped[str] = mapped_column(String(255), nullable=False)  # Tab label
    headline: Mapped[Optional[str]] = mapped_column(String(512))  # Panel heading

    # The explainer, one labelled section each
    definition: Mapped[Optional[str]] = mapped_column(Text)
    intuition: Mapped[Optional[str]] = mapped_column(Text)
    mechanism: Mapped[Optional[str]] = mapped_column(Text)
    limitation: Mapped[Optional[str]] = mapped_column(Text)
    # Where this sits in the module and what it connects to
    relevance: Mapped[Optional[str]] = mapped_column(Text)

    # [{"text": str, "type": "A" | "B"}] — A explains a concept, B is a scenario
    questions: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    # ["If I say X, they might ask ...", ...]
    followups: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Chunk indices this came from. Makes coverage checkable: a re-run
    # processes only what no concept has claimed yet.
    source_chunks: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Relationships
    profile: Mapped["SubjectProfile"] = relationship("SubjectProfile")
    transcript: Mapped["Transcript"] = relationship(
        "Transcript", back_populates="concepts"
    )
    cards: Mapped[list["Card"]] = relationship("Card", back_populates="concept")

    def __repr__(self) -> str:
        return f"<Concept {self.id} {self.title!r}>"
