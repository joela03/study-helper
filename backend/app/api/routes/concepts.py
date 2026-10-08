"""
Concept endpoints.

A concept is a lecture idea condensed into something readable before recall:
a definition, an intuition, how it works, and where it breaks down. Its
questions become the flashcards, linked back by concept_id.
"""
from datetime import datetime
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_profile
from app.models.user import User
from app.models.profile import SubjectProfile
from app.models.concept import Concept
from app.models.transcript import Transcript
from app.services.generation import CONCEPT_WINDOW_CHARS, window_chunk_indices
from app.tasks import celery_app
from app.tasks.concepts import generate_concepts_task

router = APIRouter()


class ConceptQuestion(BaseModel):
    text: str
    type: str = "A"
    answer: str = ""


class ConceptResponse(BaseModel):
    id: int
    profile_id: int
    transcript_id: int
    order_index: int
    title: str
    headline: Optional[str]
    definition: Optional[str]
    intuition: Optional[str]
    mechanism: Optional[str]
    limitation: Optional[str]
    relevance: Optional[str] = None
    worked_example: Optional[str] = None
    questions: list[ConceptQuestion] = []
    followups: list[str] = []
    card_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConceptListResponse(BaseModel):
    concepts: list[ConceptResponse]
    total: int


class GenerateConceptsRequest(BaseModel):
    transcript_id: int
    save_cards: bool = Field(
        True, description="Also create flashcards from each concept's questions"
    )


class GenerateConceptsResponse(BaseModel):
    """Acknowledgement that the job is queued, not the finished concepts."""
    task_id: str
    transcript_id: int
    status: str = "queued"
    passes: int = Field(description="How many LLM passes this lecture needs")


class ConceptJobStatus(BaseModel):
    task_id: str
    state: str  # PENDING | PROGRESS | SUCCESS | FAILURE
    stage: str | None = None
    current: int = 0
    total: int = 0
    concepts: int = 0
    cards_created: int | None = None
    covered_chunks: int = 0
    total_chunks: int = 0
    error: str | None = None


def _to_response(concept: Concept, card_count: int = 0) -> ConceptResponse:
    return ConceptResponse(
        id=concept.id,
        profile_id=concept.profile_id,
        transcript_id=concept.transcript_id,
        order_index=concept.order_index,
        title=concept.title,
        headline=concept.headline,
        definition=concept.definition,
        intuition=concept.intuition,
        mechanism=concept.mechanism,
        limitation=concept.limitation,
        relevance=concept.relevance,
        worked_example=concept.worked_example,
        questions=[ConceptQuestion(**q) for q in (concept.questions or [])],
        followups=list(concept.followups or []),
        card_count=card_count,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
    )


@router.post(
    "/from-transcript",
    response_model=GenerateConceptsResponse,
    status_code=202,
)
async def generate_concepts(
    request: GenerateConceptsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue concept extraction for a transcript.

    Returns immediately with a task id. Condensing a lecture is one LLM call
    per window plus any rate-limit waiting, which is far too long to hold a
    request open, so the work happens on the worker. Poll /jobs/{task_id}.
    """
    result = await db.execute(
        select(Transcript)
        .options(selectinload(Transcript.chunks))
        .where(Transcript.id == request.transcript_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    await get_owned_profile(transcript.profile_id, user, db)

    if not transcript.chunks:
        raise HTTPException(
            status_code=400,
            detail="Transcript has no processed chunks. Wait for processing to complete.",
        )

    ordered = [
        chunk.content
        for chunk in sorted(transcript.chunks, key=lambda c: c.chunk_index)
    ]
    # Only windows holding unclaimed chunks will actually run, so report
    # that count — otherwise the progress bar starts against the wrong total
    covered: set[int] = set()
    for concept in await db.scalars(
        select(Concept).where(Concept.transcript_id == transcript.id)
    ):
        covered.update(concept.source_chunks or [])

    windows = window_chunk_indices(ordered, CONCEPT_WINDOW_CHARS)
    passes = len([w for w in windows if any(i not in covered for i in w)])

    task = generate_concepts_task.delay(
        transcript_id=transcript.id,
        save_cards=request.save_cards,
    )

    return GenerateConceptsResponse(
        task_id=task.id,
        transcript_id=transcript.id,
        passes=passes,
    )


@router.get("/jobs/{task_id}", response_model=ConceptJobStatus)
async def get_concept_job(
    task_id: str,
    user: User = Depends(get_current_user),
):
    """Progress for a queued concept extraction."""
    result = AsyncResult(task_id, app=celery_app)
    info = result.info if isinstance(result.info, dict) else {}

    if result.state == "FAILURE":
        return ConceptJobStatus(
            task_id=task_id,
            state="FAILURE",
            error=str(result.info),
        )

    # The task returns an error key rather than raising, so a readable reason
    # survives instead of a bare FAILURE
    if result.state == "SUCCESS" and info.get("error"):
        return ConceptJobStatus(
            task_id=task_id,
            state="FAILURE",
            error=info["error"],
        )

    # On success the payload is the task's return value, which has no
    # current/total — report it as fully done so a progress bar lands at 100%
    # instead of snapping back to zero.
    if result.state == "SUCCESS":
        passes = info.get("passes", 0)
        return ConceptJobStatus(
            task_id=task_id,
            state="SUCCESS",
            stage="done",
            current=passes,
            total=passes,
            concepts=info.get("concepts_created", 0),
            cards_created=info.get("cards_created"),
            covered_chunks=info.get("covered_chunks", 0),
            total_chunks=info.get("total_chunks", 0),
        )

    return ConceptJobStatus(
        task_id=task_id,
        state=result.state,
        stage=info.get("stage"),
        current=info.get("current", 0),
        total=info.get("total", 0),
        concepts=info.get("concepts", 0),
        cards_created=info.get("cards_created"),
    )


@router.get("/", response_model=ConceptListResponse)
async def list_concepts(
    transcript_id: int | None = None,
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List concepts, newest lecture order first within each transcript."""
    query = select(Concept).options(selectinload(Concept.cards))

    if profile_id:
        await get_owned_profile(profile_id, user, db)
        query = query.where(Concept.profile_id == profile_id)
    if transcript_id:
        query = query.where(Concept.transcript_id == transcript_id)
    if not profile_id and not user.is_admin:
        query = query.where(
            Concept.profile_id.in_(
                select(SubjectProfile.id).where(SubjectProfile.user_id == user.id)
            )
        )

    result = await db.execute(
        query.order_by(Concept.transcript_id, Concept.order_index)
    )
    concepts = result.scalars().all()

    return ConceptListResponse(
        concepts=[_to_response(c, len(c.cards)) for c in concepts],
        total=len(concepts),
    )


@router.get("/{concept_id}", response_model=ConceptResponse)
async def get_concept(
    concept_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Concept)
        .options(selectinload(Concept.cards))
        .where(Concept.id == concept_id)
    )
    concept = result.scalar_one_or_none()

    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    await get_owned_profile(concept.profile_id, user, db)

    return _to_response(concept, len(concept.cards))
