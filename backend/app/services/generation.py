"""
Flashcard and content generation service using LLM APIs.
Uses cheap models for high-frequency generation tasks.
"""
import json
import logging
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI
from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy load clients
_anthropic_client: Optional[Anthropic] = None
_openai_client: Optional[OpenAI] = None
_groq_client: Optional[Groq] = None


def get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


FLASHCARD_SYSTEM_PROMPT = """You are an expert educator creating flashcards for university-level study.

Generate flashcards from the provided content. Each flashcard should:
- Have a clear, specific question that tests understanding (not just recall)
- Have a concise but complete answer
- Focus on key concepts, definitions, relationships, or applications
- Be self-contained (understandable without additional context)

Output format: Return a JSON array of flashcard objects with "question" and "answer" fields.
Example: [{"question": "What is backpropagation?", "answer": "An algorithm for training neural networks by computing gradients of the loss function with respect to weights, propagating errors backward through the network."}]

Only output valid JSON, no additional text."""


def generate_flashcards_anthropic(
    content: str,
    num_cards: int = 5,
    model: str = "claude-3-haiku-20240307",
) -> list[dict]:
    """
    Generate flashcards using Anthropic's Claude API.

    Args:
        content: Source text to generate flashcards from
        num_cards: Target number of flashcards
        model: Claude model to use (haiku for cost efficiency)

    Returns:
        List of {"question": str, "answer": str} dicts
    """
    client = get_anthropic_client()

    user_prompt = f"""Generate {num_cards} flashcards from this content:

{content}

Remember: Output only valid JSON array."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=FLASHCARD_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        response_text = response.content[0].text.strip()

        # Parse JSON
        flashcards = json.loads(response_text)

        # Validate structure
        validated = []
        for card in flashcards:
            if isinstance(card, dict) and "question" in card and "answer" in card:
                validated.append({
                    "question": str(card["question"]),
                    "answer": str(card["answer"]),
                })

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse flashcard JSON: {e}")
        logger.debug(f"Response was: {response_text}")
        return []
    except Exception as e:
        logger.exception(f"Flashcard generation failed: {e}")
        raise


def generate_flashcards_openai(
    content: str,
    num_cards: int = 5,
    model: str = "gpt-4o-mini",
) -> list[dict]:
    """
    Generate flashcards using OpenAI's API.

    Args:
        content: Source text to generate flashcards from
        num_cards: Target number of flashcards
        model: OpenAI model to use (gpt-4o-mini for cost efficiency)

    Returns:
        List of {"question": str, "answer": str} dicts
    """
    client = get_openai_client()

    user_prompt = f"""Generate {num_cards} flashcards from this content:

{content}

Remember: Output only valid JSON array."""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": FLASHCARD_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        response_text = response.choices[0].message.content.strip()

        # Parse JSON - OpenAI may wrap in {"flashcards": [...]}
        data = json.loads(response_text)

        if isinstance(data, list):
            flashcards = data
        elif isinstance(data, dict) and "flashcards" in data:
            flashcards = data["flashcards"]
        else:
            flashcards = []

        # Validate structure
        validated = []
        for card in flashcards:
            if isinstance(card, dict) and "question" in card and "answer" in card:
                validated.append({
                    "question": str(card["question"]),
                    "answer": str(card["answer"]),
                })

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse flashcard JSON: {e}")
        return []
    except Exception as e:
        logger.exception(f"Flashcard generation failed: {e}")
        raise


def generate_flashcards_groq(
    content: str,
    num_cards: int = 5,
    model: str = "qwen/qwen3.8-27b",
) -> list[dict]:
    """
    Generate flashcards using Groq's API (free tier).

    Args:
        content: Source text to generate flashcards from
        num_cards: Target number of flashcards
        model: Groq model to use
            - qwen/qwen3.8-27b: Good quality
            - groq/compound: Groq's compound model
            - openai/gpt-oss-120b: Largest available

    Returns:
        List of {"question": str, "answer": str} dicts
    """
    client = get_groq_client()

    user_prompt = f"""Generate {num_cards} flashcards from this content:

{content}

Remember: Output only valid JSON array."""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": FLASHCARD_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )

        response_text = response.choices[0].message.content.strip()

        # Clean up response if needed (remove markdown code blocks)
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        # Parse JSON
        flashcards = json.loads(response_text)

        # Handle wrapped responses
        if isinstance(flashcards, dict) and "flashcards" in flashcards:
            flashcards = flashcards["flashcards"]

        # Validate structure
        validated = []
        for card in flashcards:
            if isinstance(card, dict) and "question" in card and "answer" in card:
                validated.append({
                    "question": str(card["question"]),
                    "answer": str(card["answer"]),
                })

        return validated

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse flashcard JSON: {e}")
        logger.debug(f"Response was: {response_text}")
        return []
    except Exception as e:
        logger.exception(f"Flashcard generation failed: {e}")
        raise


def generate_flashcards(
    content: str,
    num_cards: int = 5,
    provider: str = "groq",
) -> list[dict]:
    """
    Generate flashcards using the specified provider.

    Args:
        content: Source text to generate flashcards from
        num_cards: Target number of flashcards
        provider: "groq", "anthropic", or "openai"

    Returns:
        List of {"question": str, "answer": str} dicts
    """
    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")
        return generate_flashcards_groq(content, num_cards)
    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        return generate_flashcards_anthropic(content, num_cards)
    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        return generate_flashcards_openai(content, num_cards)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_available_provider() -> str:
    """Return the first available LLM provider based on configured API keys."""
    if settings.GROQ_API_KEY:
        return "groq"
    elif settings.ANTHROPIC_API_KEY:
        return "anthropic"
    elif settings.OPENAI_API_KEY:
        return "openai"
    else:
        raise ValueError("No LLM API key configured. Set GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")
