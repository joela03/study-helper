"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Profile, Transcript, Card } from "@/types";
import { getProfile, getTranscripts, getCards, generateFromTranscript } from "@/lib/api";
import UploadForm from "@/components/UploadForm";

export default function ProfileDetailPage() {
  const params = useParams();
  const profileId = Number(params.id);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<number | null>(null);

  useEffect(() => {
    fetchData();
  }, [profileId]);

  async function fetchData() {
    try {
      const [profileRes, transcriptsRes, cardsRes] = await Promise.all([
        getProfile(profileId),
        getTranscripts(profileId),
        getCards(profileId),
      ]);
      setProfile(profileRes);
      setTranscripts(transcriptsRes.transcripts);
      setCards(cardsRes.cards);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateCards(transcriptId: number) {
    setGenerating(transcriptId);
    try {
      await generateFromTranscript({ transcript_id: transcriptId, num_cards: 5 });
      // Refresh cards
      const cardsRes = await getCards(profileId);
      setCards(cardsRes.cards);
    } catch (error) {
      console.error("Failed to generate cards:", error);
    } finally {
      setGenerating(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="text-center py-12">
        <h1 className="text-2xl font-bold text-red-400">Profile not found</h1>
        <Link href="/profiles" className="text-blue-400 mt-4 inline-block">
          ← Back to profiles
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link href="/profiles" className="text-gray-400 hover:text-gray-300 text-sm mb-2 inline-block">
          ← Back to profiles
        </Link>
        <h1 className="text-3xl font-bold">{profile.name}</h1>
        {profile.module_code && (
          <p className="text-gray-400 mt-1">{profile.module_code}</p>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-gray-400 text-sm">Transcripts</h3>
          <p className="text-2xl font-bold">{transcripts.length}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-gray-400 text-sm">Cards</h3>
          <p className="text-2xl font-bold">{cards.length}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <h3 className="text-gray-400 text-sm">Due Today</h3>
          <p className="text-2xl font-bold text-blue-400">{profile.due_card_count}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Transcripts */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Transcripts</h2>

          <UploadForm
            profileId={profileId}
            onUploaded={(transcript) => setTranscripts([...transcripts, transcript])}
          />

          <div className="mt-6 space-y-3">
            {transcripts.map((transcript) => (
              <div
                key={transcript.id}
                className="bg-gray-800 rounded-lg p-4 flex justify-between items-center"
              >
                <div>
                  <h3 className="font-medium">{transcript.title}</h3>
                  <div className="flex gap-3 text-sm text-gray-400 mt-1">
                    <span className={
                      transcript.status === "completed" ? "text-green-400" :
                      transcript.status === "failed" ? "text-red-400" :
                      transcript.status === "processing" ? "text-yellow-400" :
                      "text-gray-400"
                    }>
                      {transcript.status}
                    </span>
                    <span>{transcript.chunk_count} chunks</span>
                  </div>
                </div>
                {transcript.status === "completed" && (
                  <button
                    onClick={() => handleGenerateCards(transcript.id)}
                    disabled={generating === transcript.id}
                    className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded text-sm"
                  >
                    {generating === transcript.id ? "Generating..." : "Generate Cards"}
                  </button>
                )}
              </div>
            ))}
            {transcripts.length === 0 && (
              <p className="text-gray-500 text-center py-4">No transcripts yet</p>
            )}
          </div>
        </div>

        {/* Cards */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Cards</h2>
            {profile.due_card_count > 0 && (
              <Link
                href={`/review?profile=${profileId}`}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
              >
                Review Due ({profile.due_card_count})
              </Link>
            )}
          </div>

          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {cards.map((card) => (
              <div key={card.id} className="bg-gray-800 rounded-lg p-4">
                <p className="font-medium mb-2">{card.question}</p>
                <p className="text-gray-400 text-sm">{card.answer}</p>
                <div className="flex gap-3 text-xs text-gray-500 mt-2">
                  <span>Interval: {card.interval}d</span>
                  <span>Ease: {card.ease_factor.toFixed(2)}</span>
                  <span>Next: {card.next_review}</span>
                </div>
              </div>
            ))}
            {cards.length === 0 && (
              <p className="text-gray-500 text-center py-4">No cards yet. Generate from transcripts!</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
