"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Profile, Transcript, Card } from "@/types";
import {
  getProfile,
  getTranscripts,
  getCards,
  generateFromTranscript,
} from "@/lib/api";
import UploadForm from "@/components/UploadForm";
import { accentFor, rotationFor, liftOffsetFor } from "@/lib/accents";

const STATUS_TONE: Record<Transcript["status"], string> = {
  completed: "#4a6f52",
  failed: "#8d4247",
  processing: "#8a5c38",
  pending: "#6b7a85",
};

export default function ProfileDetailPage() {
  const params = useParams();
  const profileId = Number(params.id);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
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
  }, [profileId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleGenerateCards(transcriptId: number) {
    setGenerating(transcriptId);
    try {
      await generateFromTranscript({
        transcript_id: transcriptId,
        num_cards: 5,
      });
      const cardsRes = await getCards(profileId);
      setCards(cardsRes.cards);
    } catch (error) {
      console.error("Failed to generate cards:", error);
    } finally {
      setGenerating(null);
    }
  }

  if (loading) {
    return <p className="font-hand text-sm text-graphite">opening it…</p>;
  }

  if (!profile) {
    return (
      <div>
        <h1 className="font-hand text-xl">That subject isn&apos;t here.</h1>
        <Link
          href="/profiles"
          className="mt-3 inline-block font-hand text-sm text-graphite hover:text-ink"
        >
          ← back to the binder
        </Link>
      </div>
    );
  }

  const accent = accentFor(profile.id);

  return (
    <div>
      {/* The whole spread takes this subject's colour */}
      <header>
        <Link
          href="/profiles"
          className="font-hand text-xs text-graphite hover:text-ink"
        >
          ← binder
        </Link>

        <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="font-hand text-2xl" style={{ color: accent.ink }}>
            {profile.name}
          </h1>
          {profile.module_code && (
            <span className="text-sm text-graphite">{profile.module_code}</span>
          )}
        </div>

        <p className="mt-2 text-sm text-graphite">
          {transcripts.length} transcript{transcripts.length === 1 ? "" : "s"},{" "}
          {cards.length} card{cards.length === 1 ? "" : "s"}
          {profile.due_card_count > 0 && (
            <>
              {" "}
              ·{" "}
              <Link
                href={`/review?profile=${profileId}`}
                className="underline decoration-2 underline-offset-4"
                style={{ color: accent.ink }}
              >
                {profile.due_card_count} due now
              </Link>
            </>
          )}
        </p>
      </header>

      <div className="mt-11 grid grid-cols-1 gap-12 lg:grid-cols-2">
        {/* Left: transcripts, stacked like filed sheets */}
        <section>
          <h2 className="font-hand text-sm text-graphite">Lectures</h2>

          <div className="mt-4">
            <UploadForm
              profileId={profileId}
              accent={accent}
              onUploaded={(transcript) =>
                setTranscripts([...transcripts, transcript])
              }
            />
          </div>

          <div className="mt-7 space-y-5">
            {transcripts.map((transcript) => {
              const rotation = rotationFor(transcript.id, 0.7);
              return (
                <div
                  key={transcript.id}
                  className="lift"
                  style={
                    {
                      "--rot": `${rotation}deg`,
                      "--lx": `${liftOffsetFor(rotation)}px`,
                    } as React.CSSProperties
                  }
                >
                  <div className="overflow-hidden rounded-tl-lg rounded-br-lg rounded-bl-sm">
                    <div
                      className="folded relative flex items-center justify-between gap-4 p-4"
                      style={{ "--fold": "20px", backgroundColor: accent.paper } as React.CSSProperties}
                    >
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-medium text-ink">
                          {transcript.title}
                        </h3>
                        <p className="mt-1 text-xs">
                          <span style={{ color: STATUS_TONE[transcript.status] }}>
                            {transcript.status}
                          </span>
                          <span className="text-ink/50">
                            {" "}
                            · {transcript.chunk_count} chunks
                          </span>
                        </p>
                      </div>

                      {transcript.status === "completed" && (
                        <button
                          onClick={() => handleGenerateCards(transcript.id)}
                          disabled={generating === transcript.id}
                          className="shrink-0 font-hand text-xs underline decoration-2 underline-offset-4 disabled:opacity-50"
                          style={{ color: accent.ink }}
                        >
                          {generating === transcript.id
                            ? "writing…"
                            : "make cards"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {transcripts.length === 0 && (
              <p className="text-sm text-graphite">
                No lectures filed under this subject yet.
              </p>
            )}
          </div>
        </section>

        {/* Right: the card pile */}
        <section>
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="font-hand text-sm text-graphite">Cards</h2>
            {profile.due_card_count > 0 && (
              <Link
                href={`/review?profile=${profileId}`}
                className="font-hand text-xs underline decoration-2 underline-offset-4"
                style={{ color: accent.ink }}
              >
                review {profile.due_card_count} →
              </Link>
            )}
          </div>

          <div className="mt-4 max-h-[42rem] space-y-4 overflow-y-auto pr-1">
            {cards.map((card) => (
              <article
                key={card.id}
                className="rounded-[4px] border-l-2 bg-paper/70 py-2 pl-4"
                style={{ borderColor: accent.tab }}
              >
                <p className="text-sm leading-6 text-ink">{card.question}</p>
                <p className="mt-1.5 text-sm leading-6 text-graphite">
                  {card.answer}
                </p>
                <p className="mt-2 text-xs text-ink/40">
                  next {card.next_review} · {card.interval}d · ease{" "}
                  {card.ease_factor.toFixed(2)}
                </p>
              </article>
            ))}

            {cards.length === 0 && (
              <p className="text-sm text-graphite">
                No cards yet — file a lecture, then make some from it.
              </p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
