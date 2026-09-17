"""
Embedding generation service.
Creates vector embeddings for text chunks using sentence-transformers.
"""
import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings


# Reuse the model from chunking service
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedding_model


def generate_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for a single text.

    Returns:
        List of floats (384 dimensions for all-MiniLM-L6-v2)
    """
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple texts efficiently.

    Args:
        texts: List of text strings

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


def compute_similarity(text1: str, text2: str) -> float:
    """Compute semantic similarity between two texts."""
    model = get_embedding_model()
    embeddings = model.encode([text1, text2], convert_to_numpy=True)

    similarity = np.dot(embeddings[0], embeddings[1]) / (
        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
    )
    return float(similarity)


def find_similar_chunks(
    query: str,
    chunks: list[str],
    top_k: int = 5,
) -> list[tuple[int, float, str]]:
    """
    Find most similar chunks to a query (in-memory search).

    For production with many chunks, use pgvector similarity search instead.

    Returns:
        List of (index, similarity_score, chunk_text) tuples
    """
    if not chunks:
        return []

    model = get_embedding_model()

    # Encode query and all chunks
    query_embedding = model.encode(query, convert_to_numpy=True)
    chunk_embeddings = model.encode(chunks, convert_to_numpy=True)

    # Compute similarities
    similarities = []
    for i, chunk_emb in enumerate(chunk_embeddings):
        sim = np.dot(query_embedding, chunk_emb) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb)
        )
        similarities.append((i, float(sim), chunks[i]))

    # Sort by similarity (descending) and return top_k
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]
