"use client";

import { useState } from "react";
import { Card } from "@/types";
import { reviewCard, ReviewResponse } from "@/lib/api";
import { accentFor, rotationFor, liftOffsetFor } from "@/lib/accents";

interface Props {
  card: Card;
  /** Position in the session, written in the card's corner. */
  position: number;
  onReviewed: (response: ReviewResponse) => void;
  onSkip: () => void;
}

/* Muted ink-on-pastel chips rather than four saturated buttons */
const GRADES = [
  { quality: 0, label: "Forgot", paper: "#f0c9c9", ink: "#8d4247" },
  { quality: 1, label: "Hard", paper: "#eed7bd", ink: "#8a5c38" },
  { quality: 3, label: "Good", paper: "#cfdeef", ink: "#3f6b95" },
  { quality: 5, label: "Easy", paper: "#cedfd0", ink: "#4a6f52" },
];

export default function FlashcardReview({
  card,
  position,
  onReviewed,
  onSkip,
}: Props) {
  /* Keyed on card.id by the caller, so each new card mounts fresh, face up */
  const [flipped, setFlipped] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const accent = accentFor(card.profile_id);
  const rotation = rotationFor(card.id, 0.9);

  async function handleGrade(quality: number) {
    setIsSubmitting(true);
    try {
      const response = await reviewCard(card.id, quality);
      onReviewed(response);
    } catch (error) {
      console.error("Failed to submit review:", error);
    } finally {
      setIsSubmitting(false);
    }
  }

  const faceBase =
    "card-face absolute inset-0 flex flex-col rounded-[4px] border border-rule bg-paper px-8 py-7";

  return (
    <div className="mx-auto max-w-2xl">
      {/* lift (rotate + shadow filter) and card-stage (perspective) stay on
          separate elements: a filter on the perspective element can flatten
          the 3D context in some browsers */}
      <div
        className="lift"
        style={
          {
            "--rot": `${rotation}deg`,
            "--lx": `${liftOffsetFor(rotation)}px`,
          } as React.CSSProperties
        }
      >
        <div className="card-stage">
          <div
            className="card-flipper relative min-h-[21rem]"
            data-flipped={flipped}
          >
            {/* Front — question */}
            <div className={faceBase} aria-hidden={flipped}>
              <CardHeader accent={accent.tab} position={position} />

              <div className="card-ruled mt-5 flex-1 overflow-y-auto">
                <p className="text-xl leading-8 text-ink">{card.question}</p>
              </div>

              <button
                onClick={() => setFlipped(true)}
                className="mt-5 self-start font-hand text-sm text-graphite underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
              >
                turn the card over →
              </button>
            </div>

            {/* Back — answer */}
            <div className={`${faceBase} card-face-back`} aria-hidden={!flipped}>
              <CardHeader accent={accent.tab} position={position} back />

              <div className="card-ruled mt-5 flex-1 overflow-y-auto">
                <p className="text-lg leading-8 text-ink/90">{card.answer}</p>
              </div>

              <button
                onClick={() => setFlipped(false)}
                className="mt-5 self-start font-hand text-sm text-graphite underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
              >
                ← back to the question
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Grading sits on the desk below the card, not on it */}
      <div
        className={`mt-8 transition-opacity duration-300 ${
          flipped ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <p className="font-hand text-sm text-graphite">How did that go?</p>
        <div className="mt-3 flex flex-wrap gap-3">
          {GRADES.map((grade) => (
            <button
              key={grade.quality}
              onClick={() => handleGrade(grade.quality)}
              disabled={isSubmitting || !flipped}
              style={{ backgroundColor: grade.paper, color: grade.ink }}
              className="rounded-md px-5 py-2 font-hand text-sm transition-transform hover:-translate-y-0.5 disabled:opacity-50"
            >
              {grade.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-7 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-graphite">
        <button onClick={onSkip} className="hover:text-ink">
          put this one to the back
        </button>
        <span aria-hidden="true">·</span>
        <span>
          seen {card.repetitions}×, next in {card.interval}d, ease{" "}
          {card.ease_factor.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

function CardHeader({
  accent,
  position,
  back = false,
}: {
  accent: string;
  position: number;
  back?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between">
      <span
        className="h-2 w-12 rounded-full"
        style={{ backgroundColor: accent }}
        aria-hidden="true"
      />
      <span className="font-hand text-xs text-graphite">
        {back ? "answer" : `no. ${position}`}
      </span>
    </div>
  );
}
