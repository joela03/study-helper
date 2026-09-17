"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card } from "@/types";
import { getDueCards } from "@/lib/api";
import FlashcardReview from "@/components/FlashcardReview";

export default function ReviewPage() {
  const searchParams = useSearchParams();
  const profileId = searchParams.get("profile")
    ? Number(searchParams.get("profile"))
    : undefined;

  const [cards, setCards] = useState<Card[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [completed, setCompleted] = useState(0);

  useEffect(() => {
    fetchDueCards();
  }, [profileId]);

  async function fetchDueCards() {
    try {
      const res = await getDueCards(profileId);
      setCards(res.cards);
    } catch (error) {
      console.error("Failed to fetch due cards:", error);
    } finally {
      setLoading(false);
    }
  }

  function handleReviewed(updatedCard: Card) {
    setCompleted(completed + 1);
    // Move to next card
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // All done
      setCards([]);
    }
  }

  function handleSkip() {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  // No cards due
  if (cards.length === 0 && completed === 0) {
    return (
      <div className="text-center py-16">
        <h1 className="text-3xl font-bold mb-4">No Cards Due</h1>
        <p className="text-gray-400 mb-8">
          You&apos;re all caught up! Check back later for more reviews.
        </p>
        <Link
          href="/"
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium"
        >
          Back to Dashboard
        </Link>
      </div>
    );
  }

  // All done
  if (cards.length === 0 && completed > 0) {
    return (
      <div className="text-center py-16">
        <h1 className="text-3xl font-bold mb-4">Session Complete!</h1>
        <p className="text-gray-400 mb-2">
          You reviewed {completed} card{completed !== 1 ? "s" : ""}.
        </p>
        <p className="text-gray-500 mb-8">Great work! Keep it up.</p>
        <Link
          href="/"
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium"
        >
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const currentCard = cards[currentIndex];
  const remaining = cards.length - currentIndex;

  return (
    <div>
      {/* Progress */}
      <div className="mb-8">
        <div className="flex justify-between items-center mb-2">
          <h1 className="text-2xl font-bold">Review Session</h1>
          <span className="text-gray-400">
            {remaining} remaining · {completed} completed
          </span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{
              width: `${(completed / (completed + remaining)) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Card */}
      <FlashcardReview
        card={currentCard}
        onReviewed={handleReviewed}
        onSkip={handleSkip}
      />
    </div>
  );
}
