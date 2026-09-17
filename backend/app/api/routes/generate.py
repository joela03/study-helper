"""
Content generation endpoints for flashcards and practice questions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.card import Card, CardType
from app.models.transcript import Transcript, TranscriptChunk
from app.models.profile import SubjectProfile
from app.services.generation import generate_flashcards, get_available_provider
from app.services.embeddings import generate_embedding

router = APIRouter()


class GenerateFromTextRequest(BaseModel):
    """Generate flashcards from raw text."""
    profile_id: int
    content: str = Field(..., min_length=50, description="Text to generate flashcards from")
    num_cards: int = Field(5, ge=1, le=20)
    save: bool = Field(True, description="Save generated cards to database")


class GenerateFromTranscriptRequest(BaseModel):
    """Generate flashcards from a transcript's chunks."""
    transcript_id: int
    num_cards: int = Field(5, ge=1, le=20)
    save: bool = Field(True, description="Save generated cards to database")


class GenerateFromSearchRequest(BaseModel):
    """Generate flashcards from search results."""
    profile_id: int
    query: str = Field(..., min_length=3)
    num_cards: int = Field(5, ge=1, le=20)
    num_chunks: int = Field(3, ge=1, le=10, description="Number of relevant chunks to use")
    save: bool = Field(True, description="Save generated cards to database")


class GeneratedCard(BaseModel):
    question: str
    answer: str
    saved: bool = False
    card_id: int | None = None


class GenerateResponse(BaseModel):
    cards: list[GeneratedCard]
    source: str
    provider: str


@router.post("/from-text", response_model=GenerateResponse)
async def generate_from_text(
    request: GenerateFromTextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate flashcards from provided text content."""
    # Verify profile exists
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == request.profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        provider = get_available_provider()
        raw_cards = generate_flashcards(
            content=request.content,
            num_cards=request.num_cards,
            provider=provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    # Optionally save to database
    generated = []
    for card_data in raw_cards:
        saved = False
        card_id = None

        if request.save:
            card = Card(
                profile_id=request.profile_id,
                card_type=CardType.FLASHCARD,
                question=card_data["question"],
                answer=card_data["answer"],
            )
            db.add(card)
            await db.flush()
            saved = True
            card_id = card.id

        generated.append(GeneratedCard(
            question=card_data["question"],
            answer=card_data["answer"],
            saved=saved,
            card_id=card_id,
        ))

    if request.save:
        await db.commit()

    return GenerateResponse(
        cards=generated,
        source="text",
        provider=provider,
    )


@router.post("/from-transcript", response_model=GenerateResponse)
async def generate_from_transcript(
    request: GenerateFromTranscriptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate flashcards from a transcript's content."""
    # Get transcript with chunks
    result = await db.execute(
        select(Transcript)
        .options(selectinload(Transcript.chunks))
        .where(Transcript.id == request.transcript_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    if not transcript.chunks:
        raise HTTPException(
            status_code=400,
            detail="Transcript has no processed chunks. Wait for processing to complete."
        )

    # Combine chunk content
    content = "\n\n".join(
        chunk.content for chunk in sorted(transcript.chunks, key=lambda c: c.chunk_index)
    )

    try:
        provider = get_available_provider()
        raw_cards = generate_flashcards(
            content=content,
            num_cards=request.num_cards,
            provider=provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    # Optionally save to database
    generated = []
    for card_data in raw_cards:
        saved = False
        card_id = None

        if request.save:
            card = Card(
                profile_id=transcript.profile_id,
                transcript_id=transcript.id,
                card_type=CardType.FLASHCARD,
                question=card_data["question"],
                answer=card_data["answer"],
            )
            db.add(card)
            await db.flush()
            saved = True
            card_id = card.id

        generated.append(GeneratedCard(
            question=card_data["question"],
            answer=card_data["answer"],
            saved=saved,
            card_id=card_id,
        ))

    if request.save:
        await db.commit()

    return GenerateResponse(
        cards=generated,
        source=f"transcript:{transcript.id}",
        provider=provider,
    )


@router.post("/from-search", response_model=GenerateResponse)
async def generate_from_search(
    request: GenerateFromSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate flashcards from chunks matching a search query."""
    from sqlalchemy import text

    # Verify profile exists
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == request.profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Search for relevant chunks
    query_embedding = generate_embedding(request.query)
    embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

    sql = text("""
        SELECT tc.content
        FROM transcript_chunks tc
        JOIN transcripts t ON tc.transcript_id = t.id
        WHERE t.profile_id = :profile_id
        ORDER BY tc.embedding <=> cast(:embedding as vector)
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {"embedding": embedding_str, "profile_id": request.profile_id, "limit": request.num_chunks}
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No content found for this profile. Upload and process transcripts first."
        )

    # Combine relevant chunks
    content = "\n\n".join(row.content for row in rows)

    try:
        provider = get_available_provider()
        raw_cards = generate_flashcards(
            content=content,
            num_cards=request.num_cards,
            provider=provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

    # Optionally save to database
    generated = []
    for card_data in raw_cards:
        saved = False
        card_id = None

        if request.save:
            card = Card(
                profile_id=request.profile_id,
                card_type=CardType.FLASHCARD,
                question=card_data["question"],
                answer=card_data["answer"],
            )
            db.add(card)
            await db.flush()
            saved = True
            card_id = card.id

        generated.append(GeneratedCard(
            question=card_data["question"],
            answer=card_data["answer"],
            saved=saved,
            card_id=card_id,
        ))

    if request.save:
        await db.commit()

    return GenerateResponse(
        cards=generated,
        source=f"search:{request.query}",
        provider=provider,
    )
