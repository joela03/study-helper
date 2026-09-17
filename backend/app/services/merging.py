"""
Text merging service.
Combines document text and audio transcription intelligently.
"""


def merge_document_and_audio(
    document_text: str | None,
    audio_text: str | None,
) -> str:
    """
    Merge document (slides/PDF) text with audio transcription.

    The document provides structure (slide boundaries, headings).
    The audio provides spoken content not on slides.

    For MVP, we concatenate with clear section markers.
    Future enhancement: align audio segments with slides using timestamps.

    Args:
        document_text: Extracted text from PDF/slides
        audio_text: Whisper transcription from audio

    Returns:
        Merged text combining both sources
    """
    parts = []

    if document_text and document_text.strip():
        parts.append("=== DOCUMENT CONTENT ===\n")
        parts.append(document_text.strip())

    if audio_text and audio_text.strip():
        if parts:
            parts.append("\n\n")
        parts.append("=== AUDIO TRANSCRIPTION ===\n")
        parts.append(audio_text.strip())

    if not parts:
        return ""

    return "".join(parts)


def merge_with_alignment(
    document_text: str | None,
    audio_text: str | None,
    slide_timestamps: list[tuple[int, float]] | None = None,
) -> str:
    """
    Advanced merge that aligns audio segments with document sections.

    Args:
        document_text: Extracted text with [Slide N] or [Page N] markers
        audio_text: Transcription with [MM:SS] timestamps
        slide_timestamps: Optional list of (slide_number, start_time_seconds)

    Returns:
        Merged text with audio aligned to relevant slides

    Note: This is a placeholder for future enhancement.
    Implementing proper alignment requires:
    1. Slide change detection from video/audio cues
    2. Or manual timestamp input
    3. Or using an LLM to semantically match segments
    """
    # For now, fall back to simple concatenation
    # TODO: Implement proper alignment when slide_timestamps available
    return merge_document_and_audio(document_text, audio_text)
