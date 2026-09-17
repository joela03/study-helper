import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.profile import SubjectProfile
from app.models.transcript import Transcript, TranscriptStatus
from app.schemas.transcript import TranscriptResponse, TranscriptListResponse
from app.tasks.transcription import process_transcript

router = APIRouter()


@router.post("/", response_model=TranscriptResponse, status_code=201)
async def create_transcript(
    profile_id: int = Form(...),
    title: str = Form(...),
    document: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    # Verify profile exists
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.id == profile_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Profile not found")

    if not document and not audio:
        raise HTTPException(
            status_code=400,
            detail="At least one of document or audio must be provided"
        )

    # Create transcript record
    transcript = Transcript(
        profile_id=profile_id,
        title=title,
        status=TranscriptStatus.PENDING,
    )
    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)

    # Save files
    upload_dir = Path(settings.UPLOAD_DIR) / str(transcript.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    if document:
        doc_path = upload_dir / document.filename
        with open(doc_path, "wb") as f:
            content = await document.read()
            f.write(content)
        transcript.document_path = str(doc_path)

    if audio:
        audio_path = upload_dir / audio.filename
        with open(audio_path, "wb") as f:
            content = await audio.read()
            f.write(content)
        transcript.audio_path = str(audio_path)

    await db.commit()

    # Queue async processing
    process_transcript.delay(transcript.id)

    return TranscriptResponse(
        **{k: v for k, v in transcript.__dict__.items() if not k.startswith("_")},
        chunk_count=0,
    )


@router.get("/", response_model=TranscriptListResponse)
async def list_transcripts(
    profile_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Transcript).options(selectinload(Transcript.chunks))

    if profile_id:
        query = query.where(Transcript.profile_id == profile_id)

    result = await db.execute(query.offset(skip).limit(limit))
    transcripts = result.scalars().all()

    count_query = select(func.count(Transcript.id))
    if profile_id:
        count_query = count_query.where(Transcript.profile_id == profile_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return TranscriptListResponse(
        transcripts=[
            TranscriptResponse(
                **{k: v for k, v in t.__dict__.items() if not k.startswith("_")},
                chunk_count=len(t.chunks),
            )
            for t in transcripts
        ],
        total=total,
    )


@router.get("/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript(
    transcript_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transcript)
        .options(selectinload(Transcript.chunks))
        .where(Transcript.id == transcript_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return TranscriptResponse(
        **{k: v for k, v in transcript.__dict__.items() if not k.startswith("_")},
        chunk_count=len(transcript.chunks),
    )


@router.delete("/{transcript_id}", status_code=204)
async def delete_transcript(
    transcript_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transcript).where(Transcript.id == transcript_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    # Clean up files
    if transcript.document_path and os.path.exists(transcript.document_path):
        os.remove(transcript.document_path)
    if transcript.audio_path and os.path.exists(transcript.audio_path):
        os.remove(transcript.audio_path)

    await db.delete(transcript)
    await db.commit()
