"""
Audio transcription service using faster-whisper.

faster-whisper is an optional dependency and is not installed by default:
lectures usually arrive with a transcript already, and the model is the
single largest thing the worker would otherwise load. The import is deferred
so the rest of the pipeline runs without it.
"""
from pathlib import Path

from app.core.config import settings


class AudioTranscriptionUnavailable(RuntimeError):
    """Raised when audio arrives but Whisper isn't installed or enabled."""


def _load_whisper():
    if not settings.ENABLE_AUDIO_TRANSCRIPTION:
        raise AudioTranscriptionUnavailable(
            "Audio transcription is turned off. Paste the lecture transcript "
            "instead, or set ENABLE_AUDIO_TRANSCRIPTION=true after installing "
            "faster-whisper."
        )
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise AudioTranscriptionUnavailable(
            "faster-whisper isn't installed. Add it to requirements.txt and "
            "rebuild, or paste the transcript instead."
        ) from e
    return WhisperModel


# Lazy load model to avoid loading on import
_model = None


def get_whisper_model(model_size: str = "base"):
    """
    Get or initialize the Whisper model.

    Model sizes: tiny, base, small, medium, large-v2, large-v3
    - tiny/base: Fast, lower accuracy, good for dev
    - small/medium: Balanced
    - large-v2/v3: Best accuracy, slower, needs more RAM
    """
    global _model
    if _model is None:
        WhisperModel = _load_whisper()
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
