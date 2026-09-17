from typing import TYPE_CHECKING, Optional
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import SubjectProfile


class TranscriptStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Transcript(Base, TimestampMixin):
    """
    Document + audio pair per lecture.
    Audio is transcribed via Whisper and merged with document/slide text.
    """
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # File paths (relative to upload dir)
    document_path: Mapped[Optional[str]] = mapped_column(String(512))
    audio_path: Mapped[Optional[str]] = mapped_column(String(512))

    # Content
    document_text: Mapped[Optional[str]] = mapped_column(Text)  # Extracted from slides/PDF
    audio_text: Mapped[Optional[str]] = mapped_column(Text)  # Whisper transcription
    merged_text: Mapped[Optional[str]] = mapped_column(Text)  # Combined content

    status: Mapped[TranscriptStatus] = mapped_column(
        Enum(TranscriptStatus), default=TranscriptStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    profile: Mapped["SubjectProfile"] = relationship("SubjectProfile", back_populates="transcripts")
    chunks: Mapped[list["TranscriptChunk"]] = relationship(
        "TranscriptChunk", back_populates="transcript", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Transcript {self.title}>"


class TranscriptChunk(Base, TimestampMixin):
    """
    Semantic chunk of a transcript.
    Split at topic boundaries via embedding similarity, not fixed size.
    """
    __tablename__ = "transcript_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"))

    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # Order in transcript

    # pgvector embedding (384 dims for all-MiniLM-L6-v2)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(384))

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<TranscriptChunk {self.transcript_id}:{self.chunk_index}>"
