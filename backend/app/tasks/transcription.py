"""
Async transcription task using Celery.
Orchestrates the full ingestion pipeline:
1. Document extraction
2. Audio transcription
3. Text merging
4. Semantic chunking
5. Embedding generation
"""
import logging

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_transcript(self, transcript_id: int):
    """
    Process a transcript asynchronously through the full pipeline.

    This task runs in a Celery worker, separate from the FastAPI process.
    """
    # Import here to avoid circular imports and ensure fresh DB session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.models.transcript import Transcript, TranscriptChunk, TranscriptStatus
    from app.services.extraction import extract_document_text
    from app.services.transcription import transcribe_audio
    from app.services.merging import merge_document_and_audio
    from app.services.chunking import semantic_chunk
    from app.services.embeddings import generate_embeddings_batch

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as db:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()

        if not transcript:
            logger.error(f"Transcript {transcript_id} not found")
            return {"error": f"Transcript {transcript_id} not found"}

        try:
            # Update status to processing
            transcript.status = TranscriptStatus.PROCESSING
            db.commit()
            logger.info(f"Processing transcript {transcript_id}: {transcript.title}")

            # Step 1: Extract document text
            document_text = None
            if transcript.document_path:
                logger.info(f"Extracting text from document: {transcript.document_path}")
                try:
                    document_text = extract_document_text(transcript.document_path)
                    transcript.document_text = document_text
                    logger.info(f"Extracted {len(document_text)} characters from document")
                except Exception as e:
                    logger.warning(f"Document extraction failed: {e}")

            # Step 2: Transcribe audio
            audio_text = None
            if transcript.audio_path:
                logger.info(f"Transcribing audio: {transcript.audio_path}")
                try:
                    audio_text = transcribe_audio(transcript.audio_path)
                    transcript.audio_text = audio_text
                    logger.info(f"Transcribed {len(audio_text)} characters from audio")
                except Exception as e:
                    logger.warning(f"Audio transcription failed: {e}")

            # Step 3: Merge document and audio text
            merged_text = merge_document_and_audio(document_text, audio_text)
            transcript.merged_text = merged_text
            db.commit()

            if not merged_text:
                raise ValueError("No text extracted from document or audio")

            logger.info(f"Merged text: {len(merged_text)} characters")

            # Step 4: Semantic chunking
            logger.info("Chunking text semantically...")
            chunks = semantic_chunk(
                merged_text,
                similarity_threshold=0.5,
                min_chunk_size=100,
                max_chunk_size=1500,
            )
            logger.info(f"Created {len(chunks)} chunks")

            # Step 5: Generate embeddings
            logger.info("Generating embeddings...")
            embeddings = generate_embeddings_batch(chunks)

            # Step 6: Store chunks with embeddings
            logger.info("Storing chunks in database...")
            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                chunk = TranscriptChunk(
                    transcript_id=transcript_id,
                    content=chunk_text,
                    chunk_index=i,
                    embedding=embedding,
                )
                db.add(chunk)

            # Mark as completed
            transcript.status = TranscriptStatus.COMPLETED
            transcript.error_message = None
            db.commit()

            logger.info(f"Transcript {transcript_id} processed successfully")
            return {
                "transcript_id": transcript_id,
                "status": "completed",
                "chunks_created": len(chunks),
                "document_chars": len(document_text) if document_text else 0,
                "audio_chars": len(audio_text) if audio_text else 0,
            }

        except Exception as e:
            logger.exception(f"Failed to process transcript {transcript_id}")
            transcript.status = TranscriptStatus.FAILED
            transcript.error_message = str(e)
            db.commit()

            # Retry with exponential backoff (60s, 120s, 240s)
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
