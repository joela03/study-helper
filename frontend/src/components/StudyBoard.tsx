"use client";

import { useCallback, useEffect, useState } from "react";
import { Concept, Transcript } from "@/types";
import { Accent } from "@/lib/accents";
import { generateConcepts, getConceptJob, getConcepts } from "@/lib/api";
import ConceptPanel from "@/components/ConceptPanel";

interface Props {
  profileId: number;
  accent: Accent;
  transcripts: Transcript[];
  onCardsCreated?: () => void;
}

interface JobState {
  taskId: string;
  current: number;
  total: number;
  concepts: number;
  error: string | null;
  done: boolean;
}

/**
 * Lecture tabs, then concept tabs within the selected lecture, then the
 * explainer. Concepts are generated on the worker, so the button queues the
 * job and this polls it.
 */
export default function StudyBoard({
  profileId,
  accent,
  transcripts,
  onCardsCreated,
}: Props) {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeLecture, setActiveLecture] = useState<number | null>(null);
  const [activeConcept, setActiveConcept] = useState<number | null>(null);
  const [job, setJob] = useState<JobState | null>(null);

  const ready = transcripts.filter((t) => t.status === "completed");

  const loadConcepts = useCallback(async () => {
    try {
      const res = await getConcepts({ profileId });
      setConcepts(res.concepts);
    } catch (error) {
      console.error("Failed to fetch concepts:", error);
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    loadConcepts();
  }, [loadConcepts]);

  // Poll the queued job until it settles
  useEffect(() => {
    if (!job || job.done) return;

    const timer = setInterval(async () => {
      try {
        const status = await getConceptJob(job.taskId);
        if (status.state === "SUCCESS") {
          setJob({
            taskId: job.taskId,
            current: status.total,
            total: status.total,
            concepts: status.concepts,
            error: null,
            done: true,
          });
          await loadConcepts();
          onCardsCreated?.();
        } else if (status.state === "FAILURE") {
          setJob((j) =>
            j ? { ...j, done: true, error: status.error ?? "Generation failed" } : j
          );
        } else {
          setJob((j) =>
            j
              ? {
                  ...j,
                  current: status.current,
                  total: status.total || j.total,
                  concepts: status.concepts,
                }
              : j
          );
          // Concepts are saved as each one lands, so pull them in mid-run:
          // the first is studyable while the rest are still generating
          if (status.concepts > 0) await loadConcepts();
        }
      } catch (error) {
        console.error("Failed to poll concept job:", error);
      }
    }, 3000);

    return () => clearInterval(timer);
  }, [job, loadConcepts, onCardsCreated]);

  async function handleGenerate(transcriptId: number) {
    try {
      const queued = await generateConcepts(transcriptId);
      setJob({
        taskId: queued.task_id,
        current: 0,
        total: queued.passes,
        concepts: 0,
        error: null,
        done: false,
      });
    } catch (error) {
      setJob({
        taskId: "",
        current: 0,
        total: 0,
        concepts: 0,
        error: error instanceof Error ? error.message : "Couldn't start",
        done: true,
      });
    }
  }

  if (loading) {
    return <p className="font-hand text-sm text-graphite">reading back…</p>;
  }

  if (ready.length === 0) {
    return (
      <p className="text-sm text-graphite">
        Once a lecture finishes processing it can be condensed into concepts.
      </p>
    );
  }

  // Derived rather than stored: defaults to the first lecture that has
  // concepts, until the user picks one
  const defaultLecture =
    ready.find((t) => concepts.some((c) => c.transcript_id === t.id)) ??
    ready[0];
  const selectedLecture = activeLecture ?? defaultLecture?.id ?? null;

  const lectureConcepts = concepts
    .filter((c) => c.transcript_id === selectedLecture)
    .sort((a, b) => a.order_index - b.order_index);

  const current =
    lectureConcepts.find((c) => c.id === activeConcept) ?? lectureConcepts[0];

  const running = job && !job.done;
  const percent =
    job && job.total > 0 ? Math.round((job.current / job.total) * 100) : 0;

  return (
    <div>
      {/* One tab per lecture, so you can come back to any of them */}
      <div className="flex flex-wrap gap-1.5">
        {ready.map((transcript) => {
          const isActive = transcript.id === selectedLecture;
          const count = concepts.filter(
            (c) => c.transcript_id === transcript.id
          ).length;
          return (
            <button
              key={transcript.id}
              onClick={() => {
                setActiveLecture(transcript.id);
                setActiveConcept(null);
              }}
              className="rounded-t-md px-3 py-1.5 font-hand text-xs transition-colors"
              style={
                isActive
                  ? { backgroundColor: accent.tab, color: accent.ink }
                  : { color: "var(--color-graphite)" }
              }
            >
              {transcript.title}
              {count > 0 && <span className="ml-1.5 opacity-60">{count}</span>}
            </button>
          );
        })}
      </div>

      <div
        className="rounded-b-md rounded-tr-md border p-5"
        style={{ borderColor: accent.tab }}
      >
        {lectureConcepts.length === 0 ? (
          <div>
            <p className="text-sm text-graphite">
              This lecture hasn&apos;t been condensed yet.
            </p>
            {!running && (
              <button
                onClick={() => selectedLecture && handleGenerate(selectedLecture)}
                className="mt-3 rounded-md px-4 py-2 font-hand text-sm transition-transform hover:-translate-y-0.5"
                style={{ backgroundColor: accent.tab, color: accent.ink }}
              >
                Condense into concepts
              </button>
            )}
          </div>
        ) : (
          <>
            {/* Concept tabs within the lecture */}
            <div className="flex flex-wrap gap-2">
              {lectureConcepts.map((concept) => {
                const isActive = concept.id === current?.id;
                return (
                  <button
                    key={concept.id}
                    onClick={() => setActiveConcept(concept.id)}
                    className="rounded-md border px-3 py-1.5 font-hand text-xs transition-colors"
                    style={
                      isActive
                        ? {
                            backgroundColor: accent.paper,
                            borderColor: accent.tab,
                            color: accent.ink,
                          }
                        : {
                            borderColor: "var(--color-rule)",
                            color: "var(--color-graphite)",
                          }
                    }
                  >
                    {concept.title}
                  </button>
                );
              })}
            </div>

            {current && (
              <div className="mt-5">
                <ConceptPanel concept={current} accent={accent} />
              </div>
            )}

            {!running && (
              <button
                onClick={() => selectedLecture && handleGenerate(selectedLecture)}
                className="mt-5 font-hand text-xs text-graphite underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
              >
                cover anything missed
              </button>
            )}
          </>
        )}

        {/* Progress: one step per pass over the lecture */}
        {running && (
          <div className="mt-4">
            <div className="flex items-baseline justify-between">
              <p className="font-hand text-xs" style={{ color: accent.ink }}>
                condensing — pass {Math.max(job!.current, 1)} of {job!.total}
              </p>
              <p className="text-xs text-ink/45">
                {job!.concepts} concept{job!.concepts === 1 ? "" : "s"} so far
              </p>
            </div>
            <div className="mt-2 h-px w-full bg-rule">
              <div
                className="h-px transition-all duration-500"
                style={{ width: `${percent}%`, backgroundColor: accent.ink }}
              />
            </div>
            <p className="mt-2 text-xs text-ink/40">
              Each concept is saved as it lands, so you can start reading the
              ones above while the rest are still being worked through.
            </p>
          </div>
        )}

        {job?.error && (
          <p className="mt-4 text-sm text-[#9e4f54]">{job.error}</p>
        )}
      </div>
    </div>
  );
}
