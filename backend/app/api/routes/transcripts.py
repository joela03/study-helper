import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_owned_profile
from app.models.user import User
from app.models.profile import SubjectProfile
from app.models.transcript import Transcript, TranscriptStatus
from app.models.card import Card
from app.models.concept import Concept
from app.schemas.transcript import TranscriptResponse, TranscriptListResponse
from app.services.extraction import (
    extract_transcript_text,
    is_legacy_word_file,
    is_transcript_file,
)
from app.tasks.transcription import process_transcript

router = APIRouter()


@router.post("/", response_model=TranscriptResponse, status_code=201)
async def create_transcript(
    profile_id: int = Form(...),
    title: str = Form(...),
    document: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    transcript_text: str | None = Form(None),
    transcript_file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a transcript from any combination of a document and one source of
    spoken content.

    Spoken content can arrive three ways, and all three end up in audio_text
    so the rest of the pipeline is unchanged:

    - transcript_text: pasted in, already transcribed elsewhere (Panopto)
    - transcript_file: a .txt/.md/.docx export of the same
    - audio: an actual recording, which Whisper transcribes on the worker

    A text-looking file sent in the audio field is re-routed here rather than
    handed to Whisper, so the caller does not have to get the field right.
    """
    await get_owned_profile(profile_id, user, db)

    pasted_text = transcript_text.strip() if transcript_text else None

    # Legacy .doc can be read by neither python-docx nor Whisper
    for candidate in (audio, transcript_file):
        if candidate and is_legacy_word_file(candidate.filename):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Legacy .doc files can't be read. "
                    "Save it as .docx or .txt, or paste the text in."
                ),
            )

    # Background check: a transcript sent in the audio field is still a
    # transcript. Re-route it instead of sending a text file to Whisper.
    if audio and is_transcript_file(audio.filename) and not transcript_file:
        transcript_file = audio
        audio = None

    # Fail here rather than queueing work the worker can't do
    if audio and not settings.ENABLE_AUDIO_TRANSCRIPTION:
        raise HTTPException(
            status_code=400,
            detail=(
                "Audio transcription is turned off. Paste the lecture "
                "transcript, or upload it as .txt, .md or .docx."
            ),
        )

    if transcript_file and not is_transcript_file(transcript_file.filename):
        raise HTTPException(
            status_code=400,
            detail="Transcript files must be .txt, .md or .docx",
        )

    sources = [s for s in (audio, pasted_text, transcript_file) if s]
    if not document and not sources:
        raise HTTPException(
            status_code=400,
            detail="Provide a document, an audio file, or a transcript",
        )

    if len(sources) > 1:
        raise HTTPException(
            status_code=400,
            detail="Provide only one of audio, transcript_text or transcript_file",
        )

    # Create transcript record
    transcript = Transcript(
        profile_id=profile_id,
        title=title,
        status=TranscriptStatus.PENDING,
        audio_text=pasted_text,
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

    if transcript_file:
        saved = upload_dir / transcript_file.filename
        with open(saved, "wb") as f:
            content = await transcript_file.read()
            f.write(content)

        # Read it now rather than on the worker: these are small text files,
        # and failing here gives the user an error instead of a failed job.
        try:
            extracted = extract_transcript_text(str(saved)).strip()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Couldn't read that transcript file: {e}",
            )

        if not extracted:
            raise HTTPException(
                status_code=400,
                detail="That transcript file appears to be empty",
            )

        transcript.audio_text = extracted

    await db.commit()

    # Queue async processing
    process_transcript.delay(transcript.id)

    # Refresh to get timestamps
    await db.refresh(transcript)

    return TranscriptResponse(
        id=transcript.id,
        profile_id=transcript.profile_id,
        title=transcript.title,
        status=transcript.status,
        document_path=transcript.document_path,
        audio_path=transcript.audio_path,
        error_message=transcript.error_message,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
        chunk_count=0,
    )


@router.get("/", response_model=TranscriptListResponse)
async def list_transcripts(
    profile_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Transcript).options(selectinload(Transcript.chunks))

    if profile_id:
        await get_owned_profile(profile_id, user, db)
        query = query.where(Transcript.profile_id == profile_id)
    elif not user.is_admin:
        query = query.where(
            Transcript.profile_id.in_(
                select(SubjectProfile.id).where(SubjectProfile.user_id == user.id)
            )
        )

    result = await db.execute(query.offset(skip).limit(limit))
    transcripts = result.scalars().all()

    count_query = select(func.count(Transcript.id))
    if profile_id:
        count_query = count_query.where(Transcript.profile_id == profile_id)
    elif not user.is_admin:
        count_query = count_query.where(
            Transcript.profile_id.in_(
                select(SubjectProfile.id).where(SubjectProfile.user_id == user.id)
            )
        )
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return TranscriptListResponse(
        transcripts=[
            TranscriptResponse(
                id=t.id,
                profile_id=t.profile_id,
                title=t.title,
                status=t.status,
                document_path=t.document_path,
                audio_path=t.audio_path,
                error_message=t.error_message,
                created_at=t.created_at,
                updated_at=t.updated_at,
                chunk_count=len(t.chunks),
            )
            for t in transcripts
        ],
        total=total,
    )


@router.get("/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript(
    transcript_id: int,
    user: User = Depends(get_current_user),
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

    await get_owned_profile(transcript.profile_id, user, db)

    return TranscriptResponse(
        id=transcript.id,
        profile_id=transcript.profile_id,
        title=transcript.title,
        status=transcript.status,
        document_path=transcript.document_path,
        audio_path=transcript.audio_path,
        error_message=transcript.error_message,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
        chunk_count=len(transcript.chunks),
    )


@router.delete("/{transcript_id}", status_code=204)
async def delete_transcript(
    transcript_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transcript).where(Transcript.id == transcript_id)
    )
    transcript = result.scalar_one_or_none()

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    await get_owned_profile(transcript.profile_id, user, db)

    # Cards point at the transcript with a plain foreign key and no cascade,
    # so they have to go first or the delete fails outright. Deleting a
    # lecture discards the cards made from it, review history included.
    await db.execute(delete(Card).where(Card.transcript_id == transcript_id))

    # Chunks and concepts cascade from the relationship, but clearing them
    # explicitly keeps the ordering obvious
    await db.execute(delete(Concept).where(Concept.transcript_id == transcript_id))

    # Clean up files
    if transcript.document_path and os.path.exists(transcript.document_path):
        os.remove(transcript.document_path)
    if transcript.audio_path and os.path.exists(transcript.audio_path):
        os.remove(transcript.audio_path)

    await db.delete(transcript)
    await db.commit()
