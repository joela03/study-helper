"""
Concept extraction as a background task.

Condensing a lecture means one LLM call per window, and free-tier rate limits
add waiting on top, so this runs on the worker rather than holding an HTTP
request open. Progress is reported per pass so the UI can show where it is.
"""
import logging
from datetime import datetime, timezone

from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0)
def generate_concepts_task(
    self,
    transcript_id: int,
    save_cards: bool = True,
):
    """
    Condense a processed transcript into concepts, and cards from them.

    Additive: a re-run only visits chunks no concept has claimed yet, so
    existing concepts and their cards' review history are never destroyed.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.config import settings
    from app.models.card import Card, CardType
    from app.models.concept import Concept
    from app.models.material import CourseMaterial, MaterialKind
    from app.models.profile import SubjectProfile
    from app.models.transcript import Transcript
    from app.services.generation import (
        CONCEPT_WINDOW_CHARS,
        _hash_materials,
        build_course_context,
        generate_concept_prompt,
        generate_concepts_progressive,
        get_available_provider,
        window_chunk_indices,
    )

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as db:
        transcript = db.query(Transcript).filter(
            Transcript.id == transcript_id
        ).first()

        if not transcript:
            return {"error": f"Transcript {transcript_id} not found"}

        chunks = sorted(transcript.chunks, key=lambda c: c.chunk_index)
        if not chunks:
            return {"error": "Transcript has no processed chunks"}

        ordered = [c.content for c in chunks]
        all_windows = window_chunk_indices(ordered, CONCEPT_WINDOW_CHARS)

        # What previous runs already claimed. A re-run adds to this rather
        # than wiping it, so review history on existing cards survives.
        existing = db.query(Concept).filter(
            Concept.transcript_id == transcript.id
        ).order_by(Concept.order_index).all()

        covered: set[int] = set()
        for c in existing:
            covered.update(c.source_chunks or [])

        prior_titles = [c.title for c in existing]
        next_index = len(existing)

        pending = [w for w in all_windows if any(i not in covered for i in w)]
        total_passes = len(pending)

        if not pending:
            return {
                "transcript_id": transcript_id,
                "concepts_created": 0,
                "cards_created": 0,
                "passes": 0,
                "covered_chunks": len(covered),
                "total_chunks": len(ordered),
                "note": "Every chunk is already covered by a concept",
                "provider": "none",
            }

        self.update_state(
            state="PROGRESS",
            meta={
                "stage": "starting",
                "current": 0,
                "total": total_passes,
                "concepts": 0,
            },
        )

        counters = {"concepts": 0, "cards": 0, "index": next_index, "exam_notes": 0}

        def report(current: int, total: int, so_far: int) -> None:
            self.update_state(
                state="PROGRESS",
                meta={
                    "stage": "condensing",
                    "current": current,
                    "total": total,
                    "concepts": counters["concepts"],
                },
            )

        def persist(data: dict, window: list[int]) -> None:
            """
            Save as soon as a concept exists, so it can be studied while the
            rest of the lecture is still being generated.
            """
            concept = Concept(
                profile_id=transcript.profile_id,
                transcript_id=transcript.id,
                order_index=counters["index"],
                title=data["title"],
                headline=data["headline"],
                definition=data["definition"],
                intuition=data["intuition"],
                mechanism=data["mechanism"],
                limitation=data["limitation"],
                relevance=data.get("relevance"),
                worked_example=data.get("worked_example"),
                marks_lost=data.get("marks_lost"),
                exam_note=data.get("exam_note"),
                questions=data["questions"],
                followups=data["followups"],
                source_chunks=window,
            )
            db.add(concept)
            db.flush()

            if save_cards:
                for question in data["questions"]:
                    answer = (question.get("answer") or "").strip()
                    if not answer:
                        continue
                    db.add(Card(
                        profile_id=transcript.profile_id,
                        transcript_id=transcript.id,
                        concept_id=concept.id,
                        card_type=(
                            CardType.PRACTICE_QUESTION
                            if question.get("type") == "B"
                            else CardType.FLASHCARD
                        ),
                        question=question["text"],
                        answer=answer,
                    ))
                    counters["cards"] += 1

            # A slide describing the assessment is worth more as course
            # context than as a concept: promote it so the next prompt
            # regeneration knows about it.
            note = (data.get("exam_note") or "").strip()
            if note:
                db.add(CourseMaterial(
                    profile_id=transcript.profile_id,
                    kind=MaterialKind.EXAM_INFO,
                    title=f"Assessment details from {transcript.title}"[:255],
                    content=note,
                ))
                # Not regenerated mid-run: the remaining windows would then
                # be given different instructions from the earlier ones
                profile.prompt_materials_hash = None
                counters["exam_notes"] += 1

            db.commit()
            counters["concepts"] += 1
            counters["index"] += 1

        # Standing context for this subject: outline, past papers, notes
        materials = db.query(CourseMaterial).filter(
            CourseMaterial.profile_id == transcript.profile_id
        ).all()
        material_tuples = [
            (m.kind.value, m.title, m.content or "")
            for m in materials
            if m.include_in_context
        ]
        course_context = build_course_context(material_tuples)

        profile = db.query(SubjectProfile).filter(
            SubjectProfile.id == transcript.profile_id
        ).first()

        # One prompt per subject, written from its own materials. Generated
        # on first use and reused across every window, so all 25 passes of a
        # lecture are given identical instructions.
        current_hash = _hash_materials(material_tuples)
        concept_prompt = profile.concept_prompt

        needs_prompt = not concept_prompt or (
            not profile.prompt_is_custom
            and profile.prompt_materials_hash != current_hash
        )

        if needs_prompt and material_tuples:
            logger.info("Writing a subject prompt from its course materials")
            written = generate_concept_prompt(material_tuples)
            if written:
                profile.concept_prompt = written
                profile.prompt_materials_hash = current_hash
                profile.prompt_updated_at = datetime.now(timezone.utc)
                profile.prompt_is_custom = False
                db.commit()
                concept_prompt = written
            else:
                logger.warning("Falling back to the built-in prompt")

        logger.info(
            f"{len(material_tuples)} materials in context; "
            f"prompt={'subject' if concept_prompt else 'built-in'}"
        )

        try:
            provider = get_available_provider()
            generate_concepts_progressive(
                chunks=ordered,
                provider=provider,
                on_progress=report,
                on_concept=persist,
                skip_chunks=covered,
                prior_titles=prior_titles,
                course_context=course_context,
                concept_prompt=concept_prompt,
            )
        except Exception as e:
            logger.exception(f"Concept generation failed for {transcript_id}")
            # Whatever was persisted before the failure is kept
            return {
                "error": str(e),
                "transcript_id": transcript_id,
                "concepts_created": counters["concepts"],
                "cards_created": counters["cards"],
            }

        for c in db.query(Concept).filter(Concept.transcript_id == transcript.id):
            covered.update(c.source_chunks or [])

        logger.info(
            f"Transcript {transcript_id}: +{counters['concepts']} concepts, "
            f"+{counters['cards']} cards, "
            f"{counters['exam_notes']} exam notes captured, "
            f"{len(covered)}/{len(ordered)} chunks covered"
        )

        return {
            "transcript_id": transcript_id,
            "concepts_created": counters["concepts"],
            "cards_created": counters["cards"],
            "exam_notes_found": counters["exam_notes"],
            "passes": total_passes,
            "covered_chunks": len(covered),
            "total_chunks": len(ordered),
            "provider": provider,
        }
