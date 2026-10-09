from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import Boolean, ForeignKey, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import SubjectProfile


class MaterialKind(str, enum.Enum):
    OUTLINE = "outline"  # Module description: what the course covers, how it's assessed
    PAST_PAPER = "past_paper"
    PROBLEM_SHEET = "problem_sheet"
    NOTES = "notes"  # Anything typed in directly
    EXAM_INFO = "exam_info"  # Assessment details found in a lecture
    OTHER = "other"


class CourseMaterial(Base, TimestampMixin):
    """
    Context about a subject that isn't a lecture: the course outline, past
    papers, problem sheets, notes.

    Added when a subject is created and topped up over time as more becomes
    available, which is why content is editable rather than write-once.
    """
    __tablename__ = "course_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))

    kind: Mapped[MaterialKind] = mapped_column(
        Enum(MaterialKind), default=MaterialKind.OTHER
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Set when it came from a file; typed-in notes have none
    file_path: Mapped[Optional[str]] = mapped_column(String(512))

    # Extracted on upload, or typed directly. Editable either way.
    content: Mapped[Optional[str]] = mapped_column(Text)

    # Lets a material stop shaping generation without being deleted
    include_in_context: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["SubjectProfile"] = relationship("SubjectProfile")

    def __repr__(self) -> str:
        return f"<CourseMaterial {self.id} {self.kind.value} {self.title!r}>"
