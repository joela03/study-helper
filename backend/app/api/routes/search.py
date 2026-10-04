"""
Semantic search endpoints using pgvector.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_profile
from app.models.user import User
from app.models.profile import SubjectProfile
from app.models.transcript import Transcript, TranscriptChunk
from app.services.embeddings import generate_embedding

router = APIRouter()


class SearchResult(BaseModel):
    chunk_id: int
    transcript_id: int
    content: str
    similarity: float

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


@router.get("/", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=3, description="Search query"),
    profile_id: int | None = Query(None, description="Filter by profile"),
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search transcript chunks using semantic similarity.

    Uses pgvector to find chunks most similar to the query.
    """
    if profile_id:
        await get_owned_profile(profile_id, user, db)

    # Generate embedding for query
    query_embedding = generate_embedding(q)

    # Build the similarity search query
    # pgvector uses <=> for cosine distance (lower = more similar)
    # We convert to similarity: 1 - distance
    # Use $1, $2 style parameters for asyncpg compatibility
    embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

    if profile_id:
        sql = text("""
            SELECT
                tc.id as chunk_id,
                tc.transcript_id,
                tc.content,
                1 - (tc.embedding <=> cast(:embedding as vector)) as similarity
            FROM transcript_chunks tc
            JOIN transcripts t ON tc.transcript_id = t.id
            WHERE t.profile_id = :profile_id
            ORDER BY tc.embedding <=> cast(:embedding as vector)
            LIMIT :limit
        """)
        result = await db.execute(
            sql,
            {"embedding": embedding_str, "profile_id": profile_id, "limit": limit}
        )
    elif user.is_admin:
        sql = text("""
            SELECT
                tc.id as chunk_id,
                tc.transcript_id,
                tc.content,
                1 - (tc.embedding <=> cast(:embedding as vector)) as similarity
            FROM transcript_chunks tc
            ORDER BY tc.embedding <=> cast(:embedding as vector)
            LIMIT :limit
        """)
        result = await db.execute(sql, {"embedding": embedding_str, "limit": limit})
    else:
        # Searching every subject you own, and no further
        owned = await db.execute(
            select(SubjectProfile.id).where(SubjectProfile.user_id == user.id)
        )
        owned_ids = [row[0] for row in owned]

        if not owned_ids:
            return SearchResponse(query=q, results=[], total=0)

        sql = text("""
            SELECT
                tc.id as chunk_id,
                tc.transcript_id,
                tc.content,
                1 - (tc.embedding <=> cast(:embedding as vector)) as similarity
            FROM transcript_chunks tc
            JOIN transcripts t ON tc.transcript_id = t.id
            WHERE t.profile_id = ANY(:profile_ids)
            ORDER BY tc.embedding <=> cast(:embedding as vector)
            LIMIT :limit
        """)
        result = await db.execute(
            sql,
            {"embedding": embedding_str, "profile_ids": owned_ids, "limit": limit},
        )

    rows = result.fetchall()

    results = [
        SearchResult(
            chunk_id=row.chunk_id,
            transcript_id=row.transcript_id,
            content=row.content,
            similarity=float(row.similarity),
        )
        for row in rows
    ]

    return SearchResponse(query=q, results=results, total=len(results))


@router.get("/chunks/{transcript_id}")
async def get_transcript_chunks(
    transcript_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all chunks for a transcript."""
    found = await db.execute(
        select(Transcript).where(Transcript.id == transcript_id)
    )
    transcript = found.scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    await get_owned_profile(transcript.profile_id, user, db)

    result = await db.execute(
        select(TranscriptChunk)
        .where(TranscriptChunk.transcript_id == transcript_id)
        .order_by(TranscriptChunk.chunk_index)
    )
    chunks = result.scalars().all()

    return {
        "transcript_id": transcript_id,
        "chunks": [
            {
                "id": c.id,
                "index": c.chunk_index,
                "content": c.content,
                "has_embedding": c.embedding is not None,
            }
            for c in chunks
        ],
        "total": len(chunks),
    }
