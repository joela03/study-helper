"""
Async transcription task using Celery.
Handles Whisper ASR and document text extraction.
"""
from app.tasks import celery_app


@celery_app.task(bind=True, max_retries=3)
def process_transcript(self, transcript_id: int):
    """
    Process a transcript asynchronously:
    1. Extract text from document (PDF/slides)
    2. Transcribe audio with Whisper
    3. Merge document + audio text
    4. Chunk semantically and generate embeddings
    """
    # Import here to avoid circular imports and ensure fresh DB session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.models.transcript import Transcript, TranscriptStatus

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as db:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()

        if not transcript:
            return {"error": f"Transcript {transcript_id} not found"}

        try:
            transcript.status = TranscriptStatus.PROCESSING
            db.commit()

            # TODO: Implement actual processing
            # 1. Document extraction (PyPDF2, python-pptx)
            # 2. Whisper transcription
            # 3. Text merging logic
            # 4. Semantic chunking
            # 5. Embedding generation

            # Placeholder: mark as completed
            transcript.status = TranscriptStatus.COMPLETED
            transcript.merged_text = "Processing not yet implemented"
            db.commit()

            return {
                "transcript_id": transcript_id,
                "status": "completed",
            }

        except Exception as e:
            transcript.status = TranscriptStatus.FAILED
            transcript.error_message = str(e)
            db.commit()

            # Retry with exponential backoff
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
