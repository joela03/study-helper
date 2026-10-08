"""
Concept extraction as a background task.

Condensing a lecture means one LLM call per window, and free-tier rate limits
add waiting on top, so this runs on the worker rather than holding an HTTP
request open. Progress is reported per pass so the UI can show where it is.
"""
import logging

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
    from app.models.material import CourseMaterial
    from app.models.transcript import Transcript
    from app.services.generation import (
        CONCEPT_WINDOW_CHARS,
        analyse_course,
        build_course_context,
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

        counters = {"concepts": 0, "cards": 0, "index": next_index}

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

            db.commit()
            counters["concepts"] += 1
            counters["index"] += 1

        # Standing context for this subject: outline, past papers, notes
        materials = db.query(CourseMaterial).filter(
            CourseMaterial.profile_id == transcript.profile_id
        ).all()
        material_tuples = [(m.kind.value, m.title, m.content or "") for m in materials]
        course_context = build_course_context(material_tuples)
        course = analyse_course(material_tuples)

        if course_context:
            logger.info(
                f"Using {len(materials)} course materials as context "
                f"(oral_exam={course['oral_exam']}, maths_heavy={course['maths_heavy']})"
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
                course=course,
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
            f"{len(covered)}/{len(ordered)} chunks covered"
        )

        return {
            "transcript_id": transcript_id,
            "concepts_created": counters["concepts"],
            "cards_created": counters["cards"],
            "passes": total_passes,
            "covered_chunks": len(covered),
            "total_chunks": len(ordered),
            "provider": provider,
        }
