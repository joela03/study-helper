"""
Audio transcription service using faster-whisper.
"""
from pathlib import Path

from faster_whisper import WhisperModel


# Lazy load model to avoid loading on import
_model = None


def get_whisper_model(model_size: str = "base") -> WhisperModel:
    """
    Get or initialize the Whisper model.

    Model sizes: tiny, base, small, medium, large-v2, large-v3
    - tiny/base: Fast, lower accuracy, good for dev
    - small/medium: Balanced
    - large-v2/v3: Best accuracy, slower, needs more RAM
    """
    global _model
    if _model is None:
        # Use CPU for compatibility; change to "cuda" if GPU available
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(file_path: str, model_size: str = "base") -> str:
    """
    Transcribe an audio file to text using Whisper.

    Args:
        file_path: Path to audio file (mp3, wav, m4a, etc.)
        model_size: Whisper model size

    Returns:
        Transcribed text with timestamps
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    model = get_whisper_model(model_size)

    segments, info = model.transcribe(
        file_path,
        beam_size=5,
        language="en",  # Auto-detect if None, but explicit is faster
        vad_filter=True,  # Filter out non-speech
    )

    # Collect segments with timestamps
    transcript_parts = []
    for segment in segments:
        # Format: [MM:SS] text
        minutes = int(segment.start // 60)
        seconds = int(segment.start % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"
        transcript_parts.append(f"{timestamp} {segment.text.strip()}")

    return "\n".join(transcript_parts)


def transcribe_audio_simple(file_path: str, model_size: str = "base") -> str:
    """
    Transcribe audio without timestamps (plain text output).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    model = get_whisper_model(model_size)

    segments, _ = model.transcribe(
        file_path,
        beam_size=5,
        language="en",
        vad_filter=True,
    )

    return " ".join(segment.text.strip() for segment in segments)
