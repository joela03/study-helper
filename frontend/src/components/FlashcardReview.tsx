"use client";

import { useState } from "react";
import { Card } from "@/types";
import { reviewCard } from "@/lib/api";

interface Props {
  card: Card;
  onReviewed: (updatedCard: Card) => void;
  onSkip: () => void;
}

export default function FlashcardReview({ card, onReviewed, onSkip }: Props) {
  const [showAnswer, setShowAnswer] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleGrade = async (quality: number) => {
    setIsSubmitting(true);
    try {
      const updated = await reviewCard(card.id, quality);
      onReviewed(updated);
      setShowAnswer(false);
    } catch (error) {
      console.error("Failed to submit review:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const gradeButtons = [
    { quality: 0, label: "Forgot", color: "bg-red-600 hover:bg-red-700" },
    { quality: 1, label: "Hard", color: "bg-orange-600 hover:bg-orange-700" },
    { quality: 3, label: "Good", color: "bg-blue-600 hover:bg-blue-700" },
    { quality: 5, label: "Easy", color: "bg-green-600 hover:bg-green-700" },
  ];

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-gray-800 rounded-lg shadow-lg p-8">
        {/* Question */}
        <div className="mb-8">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Question</h3>
          <p className="text-xl text-white">{card.question}</p>
        </div>

        {/* Answer */}
        {showAnswer ? (
          <div className="mb-8">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Answer</h3>
            <p className="text-lg text-gray-200">{card.answer}</p>
          </div>
        ) : (
          <button
            onClick={() => setShowAnswer(true)}
            className="w-full py-4 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium mb-8"
          >
            Show Answer
          </button>
        )}

        {/* Grade buttons */}
        {showAnswer && (
          <div>
            <h3 className="text-sm font-medium text-gray-400 mb-3">
              How well did you know this?
            </h3>
            <div className="grid grid-cols-4 gap-3">
              {gradeButtons.map((btn) => (
                <button
                  key={btn.quality}
                  onClick={() => handleGrade(btn.quality)}
                  disabled={isSubmitting}
                  className={`py-3 px-4 rounded-lg font-medium text-white ${btn.color} disabled:opacity-50`}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Skip button */}
        <button
          onClick={onSkip}
          className="mt-6 w-full py-2 text-gray-400 hover:text-gray-300 text-sm"
        >
          Skip this card
        </button>
      </div>

      {/* Card info */}
      <div className="mt-4 text-center text-sm text-gray-500">
        Interval: {card.interval} days · Ease: {card.ease_factor.toFixed(2)} ·
        Reviews: {card.repetitions}
      </div>
    </div>
  );
}
