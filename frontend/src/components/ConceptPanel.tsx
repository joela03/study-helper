"use client";

import { Concept } from "@/types";
import { Accent } from "@/lib/accents";

interface Props {
  concept: Concept;
  accent: Accent;
  /** Hide the questions and follow-ups — used mid-review, where the card
      on screen is already asking one of them. */
  explainerOnly?: boolean;
}

function Section({
  label,
  body,
  tone,
}: {
  label: string;
  body: string | null;
  tone: string;
}) {
  if (!body) return null;
  return (
    <p className="mt-3 text-sm leading-6 text-ink/85">
      <span className="font-hand" style={{ color: tone }}>
        {label}:{" "}
      </span>
      {body}
    </p>
  );
}

export default function ConceptPanel({
  concept,
  accent,
  explainerOnly = false,
}: Props) {
  return (
    <div className="space-y-5">
      <section
        className="rounded-tl-xl rounded-br-xl rounded-bl-sm border p-5"
        style={{
          borderColor: accent.tab,
          backgroundColor: `${accent.paper}55`,
        }}
      >
        <p className="font-hand text-xs" style={{ color: accent.ink }}>
          How to explain it
        </p>

        {concept.headline && (
          <h3 className="mt-1 text-base font-medium text-ink">
            {concept.headline}
          </h3>
        )}

        <Section
          label="One-sentence definition"
          body={concept.definition}
          tone={accent.ink}
        />
        <Section label="Intuition" body={concept.intuition} tone={accent.ink} />
        <Section
          label="How it works"
          body={concept.mechanism}
          tone={accent.ink}
        />
        <Section
          label="Key limitation to mention"
          body={concept.limitation}
          tone={accent.ink}
        />
        <Section
          label="Where this fits"
          body={concept.relevance}
          tone={accent.ink}
        />
      </section>

      {!explainerOnly && concept.questions.length > 0 && (
        <section className="rounded-tl-xl rounded-br-xl rounded-bl-sm border border-rule p-5">
          <p className="font-hand text-xs text-graphite">Sample questions</p>
          <p className="mt-0.5 text-xs text-ink/45">
            Type A = explain a concept · Type B = scenario
          </p>

          <ul className="mt-3 divide-y divide-rule">
            {concept.questions.map((question, i) => (
              <li
                key={i}
                className="flex items-start justify-between gap-4 py-3"
              >
                <div className="min-w-0">
                  <p className="text-sm leading-6 text-ink">{question.text}</p>
                  {question.answer && (
                    <p className="mt-1 text-sm leading-6 text-graphite">
                      {question.answer}
                    </p>
                  )}
                </div>
                <span
                  className="shrink-0 rounded-full px-2.5 py-0.5 font-hand text-[0.7rem]"
                  style={
                    question.type === "B"
                      ? { backgroundColor: "#cedfd0", color: "#4a6f52" }
                      : { backgroundColor: "#cfdeef", color: "#3f6b95" }
                  }
                >
                  Type {question.type}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!explainerOnly && concept.followups.length > 0 && (
        <section
          className="rounded-tl-xl rounded-br-xl rounded-bl-sm border p-5"
          style={{ borderColor: "#d9ac86" }}
        >
          <p className="font-hand text-xs" style={{ color: "#8e5f3c" }}>
            Examiner follow-ups to prepare for
          </p>
          <ul className="mt-3 divide-y divide-rule">
            {concept.followups.map((followup, i) => (
              <li key={i} className="flex gap-2 py-2.5">
                <span aria-hidden="true" style={{ color: "#8e5f3c" }}>
                  ↳
                </span>
                <span className="text-sm leading-6 text-ink/85">{followup}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
