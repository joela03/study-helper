"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, Concept } from "@/types";
import { getDueCards, getConcepts, ReviewResponse } from "@/lib/api";
import FlashcardReview from "@/components/FlashcardReview";
import ConceptPanel from "@/components/ConceptPanel";
import { useProfiles } from "@/lib/profiles-context";
import { accentFor } from "@/lib/accents";

function ReviewSession() {
  const searchParams = useSearchParams();
  const profileId = searchParams.get("profile")
    ? Number(searchParams.get("profile"))
    : undefined;

  const { profiles, refresh } = useProfiles();
  const [cards, setCards] = useState<Card[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [completed, setCompleted] = useState(0);
  const [failed, setFailed] = useState(0);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [showConcept, setShowConcept] = useState(false);

  const fetchDueCards = useCallback(async () => {
    try {
      const [res, conceptRes] = await Promise.all([
        getDueCards(profileId),
        getConcepts(profileId ? { profileId } : {}),
      ]);
      setCards(res.cards);
      setConcepts(conceptRes.concepts);
    } catch (error) {
      console.error("Failed to fetch due cards:", error);
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    fetchDueCards();
  }, [fetchDueCards]);

  const subject = profileId
    ? profiles.find((p) => p.id === profileId)
    : undefined;

  function handleReviewed(response: ReviewResponse) {
    setCompleted(completed + 1);
    setShowConcept(false);

    if (response.failed) {
      // Card was failed - add it back to the end of the queue
      setFailed(failed + 1);
      const updatedCards = [...cards];
      // Remove from current position and add to end
      updatedCards.splice(currentIndex, 1);
      updatedCards.push(response.card);
      setCards(updatedCards);
      // Don't increment index since we removed the current card
    } else {
      // Card passed - move to next
      if (currentIndex < cards.length - 1) {
        setCurrentIndex(currentIndex + 1);
      } else {
        // All done
        setCards([]);
        refresh();
      }
    }
  }

  function handleSkip() {
    setShowConcept(false);
    // Move skipped card to end of queue
    const updatedCards = [...cards];
    const skippedCard = updatedCards.splice(currentIndex, 1)[0];
    updatedCards.push(skippedCard);
    setCards(updatedCards);
    // Don't increment index since we removed the current card
  }

  if (loading) {
    return (
      <p className="font-hand text-sm text-graphite">pulling the cards…</p>
    );
  }

  if (cards.length === 0 && completed === 0) {
    return (
      <Note title="Nothing due.">
        <p className="text-sm text-graphite">
          You&apos;re caught up{subject ? ` on ${subject.name}` : ""}. Come back
          when the next batch comes round.
        </p>
      </Note>
    );
  }

  if (cards.length === 0 && completed > 0) {
    return (
      <Note title="That's the stack.">
        <p className="text-sm text-graphite">
          {completed} card{completed === 1 ? "" : "s"} reviewed
          {failed > 0 && (
            <>
              , {failed} of which came back round after a miss
            </>
          )}
          .
        </p>
      </Note>
    );
  }

  const currentCard = cards[currentIndex];
  const remaining = cards.length - currentIndex;
  const accent = subject ? accentFor(subject.id) : null;
  const cardConcept =
    concepts.find((c) => c.id === currentCard.concept_id) ?? null;

  return (
    <div>
      <div className="mx-auto max-w-2xl">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="font-hand text-xl">
            {subject ? subject.name : "Everything due"}
          </h1>
          <p className="text-xs text-graphite">
            {remaining} to go · {completed} done
            {failed > 0 && ` · ${failed} back in the pile`}
          </p>
        </div>

        {/* A pencil line filling in, not a rounded progress pill */}
        <div className="mt-3 h-px w-full bg-rule">
          <div
            className="h-px transition-all duration-500"
            style={{
              width: `${(completed / (completed + remaining)) * 100}%`,
              backgroundColor: accent ? accent.ink : "var(--color-navy)",
            }}
          />
        </div>
      </div>

      {cardConcept && (
        <div className="mx-auto mt-10 max-w-2xl">
          <button
            onClick={() => setShowConcept(!showConcept)}
            className="font-hand text-sm text-graphite underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
          >
            {showConcept
              ? "hide the explainer"
              : `remind me how ${cardConcept.title} works`}
          </button>

          {/* Collapsed by default: reading it first would hand you the answer */}
          {showConcept && (
            <div className="mt-4">
              <ConceptPanel
                concept={cardConcept}
                accent={accentFor(currentCard.profile_id)}
                explainerOnly
              />
            </div>
          )}
        </div>
      )}

      <div className="mt-12">
        <FlashcardReview
          key={currentCard.id}
          card={currentCard}
          position={completed + 1}
          onReviewed={handleReviewed}
          onSkip={handleSkip}
        />
      </div>
    </div>
  );
}

/** A torn-off note left on the desk — used for the empty and finished states. */
function Note({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="lift mx-auto max-w-md"
      style={{ "--rot": "-0.8deg", "--lx": "1.8px" } as React.CSSProperties}
    >
      <div className="overflow-hidden rounded-tl-xl rounded-br-xl rounded-bl-sm">
        <div className="folded relative bg-[#f3e3a3] p-7">
          <h1 className="font-hand text-xl text-[#8a6e1e]">{title}</h1>
          <div className="mt-2">{children}</div>
          <Link
            href="/"
            className="mt-5 inline-block font-hand text-sm text-[#8a6e1e] underline decoration-2 underline-offset-4"
          >
            back to the desk
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ReviewPage() {
  return (
    <Suspense
      fallback={
        <p className="font-hand text-sm text-graphite">pulling the cards…</p>
      }
    >
      <ReviewSession />
    </Suspense>
  );
}
