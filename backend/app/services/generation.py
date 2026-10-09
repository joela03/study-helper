"""
Flashcard and content generation service using LLM APIs.
Uses cheap models for high-frequency generation tasks.
"""
import json
import logging
import math
import time
from typing import Callable, Optional

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


# A full lecture's chunks concatenated can run to tens of thousands of
# characters, which Groq's free tier rejects outright with a 413. Roughly
# 12k characters is about 3k tokens, comfortably inside every provider here.
MAX_CONTENT_CHARS = 12_000

# Concepts use a much tighter window than flashcards. A pass yields one
# concept, so a wide window forces the model to discard most of what it
# sees: at 12k a single window spanned noise reduction, convolution, edge
# detection, Fourier and the Convolution Theorem, and only one survived.
CONCEPT_WINDOW_CHARS = 4_000


def fit_chunks_to_budget(
    chunks: list[str],
    budget: int = MAX_CONTENT_CHARS,
) -> tuple[list[str], bool]:
    """
    Pick chunks totalling no more than `budget` characters.

    Simply taking the first few chunks would draw every card from the opening
    slides, so when the source is too big this samples evenly across the whole
    thing instead, keeping the original order.

    Returns (selected chunks, whether anything was left out).
    """
    total = sum(len(c) for c in chunks)
    if not chunks or total <= budget:
        return list(chunks), False

    average = total / len(chunks)
    target = max(1, min(len(chunks), int(budget // average)))

    if target == 1:
        indices = [0]
    else:
        last = len(chunks) - 1
        indices = sorted({round(i * last / (target - 1)) for i in range(target)})

    chosen: set[int] = set()
    used = 0
    for i in indices:
        if used + len(chunks[i]) <= budget:
            chosen.add(i)
            used += len(chunks[i])

    # Chunk lengths vary, so the even spread can leave a lot of the budget
    # unspent. Top it up with whatever else fits rather than waste it.
    for i, chunk in enumerate(chunks):
        if used >= budget:
            break
        if i not in chosen and used + len(chunk) <= budget:
            chosen.add(i)
            used += len(chunk)

    selected = [chunks[i] for i in sorted(chosen)]

    # A single chunk larger than the whole budget: take a prefix of it
    if not selected:
        selected = [chunks[0][:budget]]

    return selected, True


FLASHCARD_SYSTEM_PROMPT = """You are an expert educator creating flashcards for university-level study.

Generate flashcards from the provided content. Each flashcard should:
- Have a clear, specific question that tests understanding (not just recall)
- Have a concise but complete answer
- Focus on key concepts, definitions, relationships, or applications
- Be self-contained (understandable without additional context)

Output format: Return a JSON array of flashcard objects with "question" and "answer" fields.
Example: [{"question": "What is backpropagation?", "answer": "An algorithm for training neural networks by computing gradients of the loss function with respect to weights, propagating errors backward through the network."}]

Only output valid JSON, no additional text."""


PROGRESSIVE_SYSTEM_PROMPT = """You are an expert educator building a *sequence* of flashcards that teaches a university-level topic in the order it should be learned.

You are shown one section of the material at a time, in the order it was taught, along with the cards already written for earlier sections.

Each flashcard should:
- Have a clear, specific question that tests understanding (not just recall)
- Have a concise but complete answer
- Be self-contained: a student should be able to answer it without having the lecture in front of them

Because the cards form a sequence:
- Cover a concept's prerequisites before the concepts that depend on them
- Where this section develops an idea from an earlier card, build on it explicitly — name the earlier concept and extend it, rather than re-teaching it from scratch
- Never restate a question that has already been asked
- Prefer questions that connect this section to what came before over questions that treat it in isolation

Output format: Return a JSON array of flashcard objects with "question" and "answer" fields.
Example: [{"question": "How does backpropagation use the chain rule introduced earlier?", "answer": "It applies the chain rule repeatedly from the loss backwards, multiplying local gradients at each layer to get the gradient of the loss with respect to every weight."}]

Only output valid JSON, no additional text."""

# How many previously written questions to show the model as context. Enough
# to avoid repetition and give it something to build on, without the prompt
# growing unbounded as the sequence gets longer.
PRIOR_QUESTION_CONTEXT = 12


def _max_tokens_for(num_cards: int) -> int:
    """
    Output budget per call.

    Scales with the number of cards asked for, but never past
    LLM_MAX_OUTPUT_TOKENS: providers meter the *expected* output, and Groq's
    free tier rejects a request outright if that estimate exceeds its
    per-minute allowance. Asking for more than the tier permits fails the
    whole call rather than returning a shorter answer.
    """
    return min(settings.LLM_MAX_OUTPUT_TOKENS, max(400, num_cards * 350))


class _OutputBudget:
    """
    Self-imposed rate limiting against a tokens-per-minute quota.

    Groq's free tier allows a fixed number of output tokens per minute and
    rejects whole requests once that is spent. Waiting for a 429 is the
    expensive way to learn this: the rejected request still cost the round
    trip, and the backoff is blind to how much budget is actually left.
    Tracking what has been spent in the last minute lets a pass wait exactly
    as long as it needs to.
    """

    def __init__(self) -> None:
        self._spent: list[tuple[float, int]] = []

    def _prune(self, now: float) -> None:
        self._spent = [(t, n) for t, n in self._spent if now - t < 60.0]

    def wait_for(self, estimated: int) -> None:
        limit = settings.LLM_OUTPUT_TOKENS_PER_MINUTE
        while True:
            now = time.monotonic()
            self._prune(now)
            used = sum(n for _, n in self._spent)

            if used + estimated <= limit or not self._spent:
                return

            # Sleep until the oldest spend ages out of the window
            oldest = min(t for t, _ in self._spent)
            delay = max(1.0, 60.0 - (now - oldest))
            logger.info(
                f"Output budget {used}/{limit} per minute; waiting {delay:.0f}s"
            )
            time.sleep(delay)

    def record(self, tokens: int) -> None:
        self._spent.append((time.monotonic(), tokens))


_output_budget = _OutputBudget()

# What a concept pass typically costs, used to reserve budget before the
# call. Measured at ~600 on this prompt; the actual figure replaces it.
_ESTIMATED_CONCEPT_TOKENS = 650


def _call_with_retry(fn, attempts: int = 3, base_delay: float = 20.0):
    """
    Retry a provider call through per-minute rate limits.

    The free tier's allowance refills over a minute, so backing off and
    retrying usually succeeds where failing immediately loses the window's
    work entirely.
    """
    last_error = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status != 429 and "rate_limit" not in str(e).lower():
                raise
            last_error = e
            if attempt < attempts - 1:
                delay = base_delay * (attempt + 1)
                logger.warning(
                    f"Rate limited, waiting {delay:.0f}s before retry "
                    f"{attempt + 2}/{attempts}"
                )
                time.sleep(delay)
    raise last_error


def _build_user_prompt(
    content: str,
    num_cards: int,
    prior_questions: list[str] | None = None,
) -> str:
    parts = []

    if prior_questions:
        listed = "\n".join(f"- {q}" for q in prior_questions)
        parts.append(
            "Flashcards already written for earlier sections:\n"
            f"{listed}\n\n"
            "Do not repeat any of these. Where this section develops one of "
            "those ideas further, write the new card so it builds on it.\n"
        )

    parts.append(f"Generate {num_cards} flashcards from this content:\n\n{content}\n")
    parts.append("Remember: Output only valid JSON array.")
    return "\n".join(parts)


def generate_flashcards_anthropic(
    content: str,
    num_cards: int = 5,
    model: str = "claude-3-haiku-20240307",
    system_prompt: str = FLASHCARD_SYSTEM_PROMPT,
    prior_questions: list[str] | None = None,
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

    user_prompt = _build_user_prompt(content, num_cards, prior_questions)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=_max_tokens_for(num_cards),
            system=system_prompt,
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
    system_prompt: str = FLASHCARD_SYSTEM_PROMPT,
    prior_questions: list[str] | None = None,
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

    user_prompt = _build_user_prompt(content, num_cards, prior_questions)

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=_max_tokens_for(num_cards),
            messages=[
                {"role": "system", "content": system_prompt},
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
    system_prompt: str = FLASHCARD_SYSTEM_PROMPT,
    prior_questions: list[str] | None = None,
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

    user_prompt = _build_user_prompt(content, num_cards, prior_questions)

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=_max_tokens_for(num_cards),
            messages=[
                {"role": "system", "content": system_prompt},
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
    system_prompt: str = FLASHCARD_SYSTEM_PROMPT,
    prior_questions: list[str] | None = None,
) -> list[dict]:
    """
    Generate flashcards using the specified provider.

    Args:
        content: Source text to generate flashcards from
        num_cards: Target number of flashcards
        provider: "groq", "anthropic", or "openai"
        system_prompt: Which prompt to use; pass PROGRESSIVE_SYSTEM_PROMPT
            when generating one section of an ordered sequence
        prior_questions: Questions already written, so the model can build on
            them instead of repeating them

    Returns:
        List of {"question": str, "answer": str} dicts
    """
    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")
        fn = generate_flashcards_groq
    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        fn = generate_flashcards_anthropic
    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        fn = generate_flashcards_openai
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return fn(
        content,
        num_cards,
        system_prompt=system_prompt,
        prior_questions=prior_questions,
    )


# Keys the parser depends on. A generated prompt that omits any of these
# would break every pass for that subject, so it's rejected rather than
# stored.
REQUIRED_CONCEPT_KEYS = (
    "title", "headline", "definition", "intuition",
    "mechanism", "limitation", "questions",
)

# Shares the request with ~4k of lecture text and the prior titles, so a
# verbose prompt eats the budget that should go to the material itself.
MAX_GENERATED_PROMPT_CHARS = 3_000

PROMPT_WRITER_SYSTEM = """You write extraction prompts for a study tool.

The tool reads one section of a lecture at a time and must return ONE concept as JSON. Your job is to write the instruction it follows, tailored to the specific module described below, so that a maths module and a discursive module get genuinely different instructions.

You will be shown that module's course materials: its outline, past papers, problem sheets. Read them for how the module is actually assessed — written or oral, open or closed book, mark ranges, whether questions demand calculation or argument, the notation and vocabulary it uses — and write a prompt that produces concepts a student could revise from for THAT exam.

Your output is the prompt itself. No preamble, no explanation, no code fences.

The prompt you write MUST:
- instruct the model to return a JSON array containing exactly one object, or [] for administrative sections (title slides, module codes, contents pages, reading lists)
- require these keys exactly: title, headline, definition, intuition, mechanism, limitation, questions
- define "questions" as a list of objects with keys text, type and answer, where type is "A" for an explain-a-concept question and "B" for an applied scenario
- require mathematics to be written as LaTeX between dollar signs, never as plain text or unicode
- require a "marks_lost" key: where students lose marks on this specific topic in this module's exams
- require an "exam_note" key, used only when the section itself describes the assessment, otherwise omitted

The prompt you write SHOULD, where the materials justify it:
- require "worked_example" when the module is assessed by calculation, specifying the kind of calculation its papers actually ask for
- require "followups" ONLY if the module has an oral exam, viva or presentation; omit this key entirely for a written exam
- mirror the module's own terminology and notation
- state the exam format explicitly so questions match it

The prompt you write MUST ALSO bound the length of every field, because the
whole JSON object has to come back in one response of at most 700 tokens. A
prompt that asks for more than that gets truncated mid-object and the whole
pass is lost. State limits explicitly, roughly:
- definition: one sentence
- intuition, mechanism: two sentences each
- limitation, marks_lost, relevance: one sentence each
- worked_example: at most 5 short lines, small numbers, no large matrices
  written out in full
- each question answer: two sentences

End the prompt with an instruction to output only valid JSON and nothing else.

Keep the prompt under 2500 characters. Be specific to this module, not generic."""


def _hash_materials(materials: list[tuple[str, str, str]]) -> str:
    """Fingerprint, so a prompt can tell when its source material moved on."""
    import hashlib

    joined = "\u0000".join(
        f"{kind}|{title}|{content or ''}" for kind, title, content in sorted(materials)
    )
    return hashlib.sha256(joined.encode()).hexdigest()


def generate_concept_prompt(
    materials: list[tuple[str, str, str]],
    provider: str = "groq",
) -> str | None:
    """
    Write this subject's extraction prompt from its course materials.

    Returns None when there's nothing to go on, or when the result omits a
    key the parser needs — the caller then falls back to the built-in
    prompt rather than running a whole subject through a broken one.
    """
    usable = [m for m in materials if (m[2] or "").strip()]
    if not usable:
        return None

    context = build_course_context(usable)
    if not context:
        return None

    user = (
        f"{context}\n"
        "Write the extraction prompt for this module now. Output only the "
        "prompt."
    )

    try:
        if provider == "groq":
            response = _call_with_retry(lambda: get_groq_client().chat.completions.create(
                model="qwen/qwen3.8-27b",
                max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                messages=[
                    {"role": "system", "content": PROMPT_WRITER_SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=0.4,
            ))
            text = response.choices[0].message.content
        elif provider == "anthropic":
            response = get_anthropic_client().messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                system=PROMPT_WRITER_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text
        else:
            response = get_openai_client().chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                messages=[
                    {"role": "system", "content": PROMPT_WRITER_SYSTEM},
                    {"role": "user", "content": user},
                ],
            )
            text = response.choices[0].message.content
    except Exception:
        logger.exception("Couldn't write a subject prompt; using the built-in one")
        return None

    prompt = (text or "").strip()
    if prompt.startswith("```"):
        prompt = "\n".join(prompt.split("\n")[1:-1]).strip()

    missing = [k for k in REQUIRED_CONCEPT_KEYS if k not in prompt]
    if missing:
        # Storing this would break every pass for the subject
        logger.warning(f"Generated prompt omits required keys {missing}; discarding")
        return None

    return prompt[:MAX_GENERATED_PROMPT_CHARS]


DEFAULT_CONCEPT_PROMPT = """You are an expert educator condensing a university lecture into the ideas a student needs to hold in their head.

You are shown one section of the lecture at a time, in teaching order, along with the concepts already extracted from earlier sections.

Return a JSON array containing exactly ONE object, or [] if the section is administrative (title slide, module code, contents page, learning outcomes, reading list, acknowledgements, section divider).

The object must have these keys:
- "title": 2-4 words, the label on a tab
- "headline": a short line framing the idea
- "definition": ONE sentence. What it is, plainly.
- "intuition": an analogy or mental picture that makes it click
- "mechanism": how it actually works, and how it builds on earlier concepts
- "limitation": the caveat or failure case a student should mention
- "relevance": one line on where this sits in the module
- "marks_lost": where students lose marks on this topic in written answers
- "questions": exactly 2 objects with keys "text", "type" and "answer", where type is "A" to explain a concept or "B" for an applied scenario
- "worked_example": a short worked calculation with real numbers, if the topic involves computation
- "exam_note": ONLY if this section describes the assessment itself; otherwise omit

Rules:
- Extract the single most important idea in this section. Do not invent material.
- Keep every field tight: definition one sentence, intuition and mechanism two at most.
- Always return a concept unless the section is administrative. Near-duplicates are filtered automatically afterwards, so holding one back only loses material.
- Write mathematics as LaTeX between dollar signs: $f(x,y)$ inline, $$F(u,v)$$ displayed. Never plain text or unicode symbols.

Only output valid JSON, no additional text."""


def _parse_json_array(response_text: str) -> list:
    """
    Parse a JSON array, salvaging what completed if the response was cut off.

    Output limits truncate mid-array, which makes json.loads fail on the whole
    thing and lose concepts that were already fully written. Decoding object by
    object keeps those.
    """
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    objects: list = []
    index = text.find("{")
    while index != -1:
        try:
            obj, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break
        if isinstance(obj, dict):
            objects.append(obj)
        index = text.find("{", end)

    if objects:
        logger.warning(f"Response truncated; salvaged {len(objects)} complete objects")
        return objects

    repaired = _repair_truncated_object(text)
    if repaired is not None:
        logger.warning("Response truncated mid-object; repaired to its last complete field")
        return [repaired]

    raise json.JSONDecodeError("no complete objects in response", text, 0)


def _repair_truncated_object(text: str) -> dict | None:
    """
    Rescue a single object that was cut off mid-way.

    A response that stops partway through the only object has no complete
    object to decode, so the whole window is otherwise lost. Trimming back
    to the last complete key/value pair and closing the brace gives a
    concept missing only its final field, which beats nothing at all.
    """
    start = text.find("{")
    if start == -1:
        return None

    body = text[start:]

    # Walk back from the end looking for a point that parses once closed
    for cut in range(len(body), 0, -1):
        fragment = body[:cut].rstrip()
        if not fragment.endswith(('"', "}", "]", *"0123456789")):
            continue
        fragment = fragment.rstrip(",")

        # Close whatever is still open, innermost first
        depth_curly = fragment.count("{") - fragment.count("}")
        depth_square = fragment.count("[") - fragment.count("]")
        if depth_curly < 0 or depth_square < 0:
            continue
        if fragment.count('"') % 2:
            continue

        candidate = fragment + ("]" * depth_square) + ("}" * depth_curly)
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        # Worth keeping only if the essentials survived
        if isinstance(obj, dict) and obj.get("title") and obj.get("definition"):
            return obj

    return None


# Course context rides along in every concept prompt, so it has to stay small
# next to the ~4k of lecture content and the free tier's output allowance.
COURSE_CONTEXT_CHARS = 1_800

# Two concepts whose title and definition embed this close together are the
# same idea in different words. Exact-title matching never caught pairs like
# "Spatial Domain Filtering" and "Spatial Domain Convolution".
#
# Measured on that real pair: duplicate 0.81, related-but-distinct
# ("Convolution Theorem") 0.51, unrelated 0.30-0.35. 0.70 sits in the gap.
CONCEPT_DUPLICATE_SIMILARITY = 0.70

def build_course_context(materials: list[tuple[str, str, str]]) -> str:
    """
    Condense a subject's materials into a short standing brief.

    Takes (kind, title, content) and returns a bounded string. The outline
    gets the most room — it says what the module is actually about — while
    papers and problem sheets contribute a sample so the model can see how
    the subject gets examined without the prompt ballooning.
    """
    if not materials:
        return ""

    # Outline first: it frames everything else
    order = {"outline": 0, "problem_sheet": 1, "past_paper": 2, "notes": 3}
    ranked = sorted(materials, key=lambda m: order.get(m[0], 4))

    budget = COURSE_CONTEXT_CHARS
    parts: list[str] = []

    for kind, title, content in ranked:
        if budget <= 200:
            break
        text = " ".join((content or "").split())
        if not text:
            continue
        share = min(len(text), max(200, budget // 2))
        parts.append(f"[{kind}] {title}: {text[:share]}")
        budget -= share

    if not parts:
        return ""

    return (
        "Context about this course, for framing only — do not invent "
        "material from it:\n" + "\n".join(parts) + "\n"
    )


def _concepts_from_provider(
    content: str,
    provider: str,
    prior_titles: list[str],
    course_context: str = "",
    system_prompt: str | None = None,
    brevity_hint: bool = False,
) -> list[dict]:
    """One call: a section of lecture in, structured concepts out."""
    system_prompt = system_prompt or DEFAULT_CONCEPT_PROMPT
    prompt_parts = []
    if course_context:
        prompt_parts.append(course_context)
    if prior_titles:
        listed = "\n".join(f"- {t}" for t in prior_titles)
        prompt_parts.append(
            f"Concepts already extracted from earlier sections:\n{listed}\n\n"
            "These are for context, not a reason to stay silent. Still return "
            "a concept for this section unless it is administrative — "
            "near-duplicates are filtered automatically afterwards, so "
            "withholding one only loses material. Where this section extends "
            "an idea above, name it and extract what is NEW here.\n"
        )
    prompt_parts.append(f"Extract the concepts from this section:\n\n{content}\n")
    if brevity_hint:
        # The first attempt overran the output limit, so ask for the
        # essentials only rather than the same thing again
        prompt_parts.append(
            "IMPORTANT: your previous answer was cut off because it was too "
            "long. Keep every field to one short sentence, omit "
            "worked_example entirely, and give at most one question."
        )
    prompt_parts.append("Remember: Output only valid JSON array.")
    user_prompt = "\n".join(prompt_parts)

    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not configured")
        _output_budget.wait_for(_ESTIMATED_CONCEPT_TOKENS)
        response = _call_with_retry(lambda: get_groq_client().chat.completions.create(
            model="qwen/qwen3.8-27b",
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
        ))
        usage = getattr(response, "usage", None)
        _output_budget.record(
            getattr(usage, "completion_tokens", None) or _ESTIMATED_CONCEPT_TOKENS
        )
        raw = response.choices[0].message.content
    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        response = get_anthropic_client().messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text
    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        response = get_openai_client().chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return _parse_json_array(raw)


def _clean_concept(raw: dict) -> dict | None:
    """Keep only well-formed concepts; a missing title makes one useless."""
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    questions = []
    for q in raw.get("questions") or []:
        if isinstance(q, dict) and str(q.get("text") or "").strip():
            qtype = str(q.get("type") or "A").strip().upper()
            questions.append({
                "text": str(q["text"]).strip(),
                "type": "B" if qtype == "B" else "A",
                "answer": str(q.get("answer") or "").strip(),
            })
        elif isinstance(q, str) and q.strip():
            questions.append({"text": q.strip(), "type": "A", "answer": ""})

    followups = [
        str(f).strip()
        for f in (raw.get("followups") or [])
        if str(f).strip()
    ]

    def field(name: str) -> str | None:
        value = raw.get(name)
        return str(value).strip() if value else None

    return {
        "title": title[:255],
        "headline": (field("headline") or "")[:512] or None,
        "relevance": field("relevance"),
        "definition": field("definition"),
        "intuition": field("intuition"),
        "mechanism": field("mechanism"),
        "limitation": field("limitation"),
        "worked_example": field("worked_example"),
        "marks_lost": field("marks_lost"),
        "exam_note": field("exam_note"),
        "questions": questions,
        "followups": followups,
    }


def window_chunk_indices(
    chunks: list[str],
    window_chars: int = CONCEPT_WINDOW_CHARS,
) -> list[list[int]]:
    """Same split as window_chunks, but returns indices so coverage is tracked."""
    windows: list[list[int]] = []
    current: list[int] = []
    used = 0

    for i, chunk in enumerate(chunks):
        if current and used + len(chunk) > window_chars:
            windows.append(current)
            current, used = [], 0
        current.append(i)
        used += len(chunk)

    if current:
        windows.append(current)

    return windows


def _is_duplicate_concept(
    candidate: dict,
    existing: list[str],
    threshold: float = CONCEPT_DUPLICATE_SIMILARITY,
) -> bool:
    """
    True if this concept is one we already have, worded differently.

    Compares title plus definition, because titles alone are too short to
    separate "2D Fourier Transform" from "DFT & Frequency Domain".
    """
    if not existing:
        return False

    from app.services.embeddings import get_embedding_model
    import numpy as np

    def describe(title: str, definition: str | None) -> str:
        return f"{title}. {definition or ''}".strip()

    text = describe(candidate["title"], candidate.get("definition"))

    try:
        model = get_embedding_model()
        vectors = model.encode([text] + existing, convert_to_numpy=True)
    except Exception:
        # Never block generation on the dedup check
        logger.exception("Duplicate check failed, keeping the concept")
        return False

    new, others = vectors[0], vectors[1:]
    new_norm = np.linalg.norm(new)

    for other in others:
        denominator = new_norm * np.linalg.norm(other)
        if denominator and float(np.dot(new, other) / denominator) >= threshold:
            return True

    return False


def generate_concepts_progressive(
    chunks: list[str],
    provider: str = "groq",
    window_chars: int = CONCEPT_WINDOW_CHARS,
    max_concepts: int = 60,
    on_progress: Callable[[int, int, int], None] | None = None,
    on_concept: Callable[[dict, list[int]], None] | None = None,
    skip_chunks: set[int] | None = None,
    prior_titles: list[str] | None = None,
    course_context: str = "",
    concept_prompt: str | None = None,
) -> list[dict]:
    """
    Walk the lecture in order, condensing each window into concepts.

    Each pass sees the titles already extracted, so the set reads front to
    back without repeating itself. One call per window, same as flashcard
    generation — the richer structure comes from the response, not more calls.
    """
    index_windows = window_chunk_indices(chunks, window_chars)
    if not index_windows:
        return []

    # A re-run only visits windows holding chunks no concept has claimed yet,
    # so regenerating adds to the set instead of replacing it.
    covered = skip_chunks or set()
    pending = [w for w in index_windows if any(i not in covered for i in w)]

    system_prompt = concept_prompt or DEFAULT_CONCEPT_PROMPT

    concepts: list[dict] = []
    seen: set[str] = {t.strip().lower() for t in (prior_titles or [])}
    # Title + definition of everything already held, for the similarity check
    described: list[str] = list(prior_titles or [])

    for position, window in enumerate(pending, 1):
        if len(concepts) >= max_concepts:
            break

        if on_progress:
            on_progress(position, len(pending), len(concepts))

        recent = list(seen)[-PRIOR_QUESTION_CONTEXT:]

        window_text = "\n\n".join(chunks[i] for i in window)
        raw_concepts = None

        # A window that fails to parse is otherwise lost along with all its
        # chunks, which is where most missing coverage came from. One retry,
        # asking for less, recovers the majority.
        for attempt in range(2):
            terse = attempt > 0
            try:
                raw_concepts = _concepts_from_provider(
                    content=window_text,
                    provider=provider,
                    prior_titles=recent,
                    course_context="" if terse else course_context,
                    system_prompt=system_prompt,
                    brevity_hint=terse,
                )
                break
            except json.JSONDecodeError:
                logger.warning(
                    f"Concept pass {position}/{len(pending)} returned invalid JSON"
                    + (" on retry; giving up" if terse else ", retrying with a shorter ask")
                )
            except Exception:
                # One bad window shouldn't lose the concepts already extracted
                logger.exception(f"Concept pass {position}/{len(pending)} failed, continuing")
                break

        if not raw_concepts:
            continue

        for raw in raw_concepts:
            cleaned = _clean_concept(raw)
            if not cleaned:
                continue
            key = cleaned["title"].strip().lower()
            if key in seen:
                continue

            # The model is told not to repeat itself, but it does anyway when
            # the transcript re-covers a topic the slides already taught
            if _is_duplicate_concept(cleaned, described):
                logger.info(f"Skipping near-duplicate concept: {cleaned['title']}")
                continue

            seen.add(key)
            described.append(f"{cleaned['title']}. {cleaned.get('definition') or ''}".strip())
            concepts.append(cleaned)
            # Handed over straight away so it can be saved and studied while
            # the rest of the lecture is still being worked through
            if on_concept:
                on_concept(cleaned, window)
            if len(concepts) >= max_concepts:
                break

    return concepts


def window_chunks(
    chunks: list[str],
    window_chars: int = MAX_CONTENT_CHARS,
) -> list[list[str]]:
    """Split ordered chunks into consecutive windows under the char budget."""
    windows: list[list[str]] = []
    current: list[str] = []
    used = 0

    for chunk in chunks:
        if current and used + len(chunk) > window_chars:
            windows.append(current)
            current, used = [], 0
        current.append(chunk)
        used += len(chunk)

    if current:
        windows.append(current)

    return windows


def generate_flashcards_progressive(
    chunks: list[str],
    total_cards: int,
    provider: str = "groq",
    window_chars: int = MAX_CONTENT_CHARS,
) -> list[dict]:
    """
    Walk the material in order, generating cards window by window.

    Each pass is told what has already been asked, so the deck builds up
    roughly in teaching order: foundations first, then the ideas that depend
    on them, with later cards extending earlier ones rather than repeating.

    This also covers the whole source instead of one budget's worth of it,
    which is what caps the number of usable cards in a single-shot call.
    """
    windows = window_chunks(chunks, window_chars)
    if not windows:
        return []

    per_window = max(1, math.ceil(total_cards / len(windows)))

    cards: list[dict] = []
    seen: set[str] = set()

    for index, window in enumerate(windows, 1):
        remaining = total_cards - len(cards)
        if remaining <= 0:
            break

        prior = [c["question"] for c in cards][-PRIOR_QUESTION_CONTEXT:]

        try:
            batch = generate_flashcards(
                content="\n\n".join(window),
                num_cards=min(per_window, remaining),
                provider=provider,
                system_prompt=PROGRESSIVE_SYSTEM_PROMPT,
                prior_questions=prior,
            )
        except Exception:
            # One bad window shouldn't lose the cards already written
            logger.exception(f"Pass {index}/{len(windows)} failed, continuing")
            continue

        for card in batch:
            key = card["question"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            cards.append(card)

    return cards[:total_cards]


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
