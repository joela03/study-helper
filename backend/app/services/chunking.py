"""
Semantic chunking service.
Splits text at topic boundaries using embedding similarity.
"""
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings


# Lazy load model
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedding_model


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences.
    Simple implementation - can be enhanced with NLTK/spaCy for better accuracy.
    """
    import re

    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # Filter empty and very short sentences
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def compute_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings."""
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))


def semantic_chunk(
    text: str,
    similarity_threshold: float = 0.5,
    min_chunk_size: int = 100,
    max_chunk_size: int = 1500,
) -> list[str]:
    """
    Split text into semantic chunks based on topic boundaries.

    Uses embedding similarity between consecutive sentences to detect
    topic shifts. When similarity drops below threshold, start new chunk.

    Args:
        text: Input text to chunk
        similarity_threshold: Cosine similarity threshold for topic boundary
        min_chunk_size: Minimum characters per chunk
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of text chunks
    """
    sentences = split_into_sentences(text)

    if not sentences:
        return [text] if text.strip() else []

    if len(sentences) == 1:
        return sentences

    model = get_embedding_model()

    # Get embeddings for all sentences
    embeddings = model.encode(sentences, convert_to_numpy=True)

    chunks = []
    current_chunk = [sentences[0]]
    current_length = len(sentences[0])

    for i in range(1, len(sentences)):
        similarity = compute_similarity(embeddings[i-1], embeddings[i])
        sentence_length = len(sentences[i])

        # Decide whether to start a new chunk
        should_split = (
            similarity < similarity_threshold
            and current_length >= min_chunk_size
        )

        would_exceed_max = current_length + sentence_length > max_chunk_size

        if should_split or would_exceed_max:
            # Save current chunk and start new one
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentences[i]]
            current_length = sentence_length
        else:
            # Add to current chunk
            current_chunk.append(sentences[i])
            current_length += sentence_length

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def fixed_size_chunk(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[str]:
    """
    Fallback: Split text into fixed-size chunks with overlap.
    Use when semantic chunking is too slow or text is very long.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence end within last 20% of chunk
            search_start = end - int(chunk_size * 0.2)
            for punct in ['. ', '! ', '? ', '\n']:
                last_punct = text.rfind(punct, search_start, end)
                if last_punct != -1:
                    end = last_punct + 1
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return chunks
