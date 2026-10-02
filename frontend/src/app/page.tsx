"use client";

import Link from "next/link";
import { useProfiles } from "@/lib/profiles-context";
import FolderCard from "@/components/FolderCard";

export default function Desk() {
  const { profiles, loading } = useProfiles();

  const totalDue = profiles.reduce((sum, p) => sum + p.due_card_count, 0);
  const subjectsWithDue = profiles.filter((p) => p.due_card_count > 0).length;

  if (loading) {
    return (
      <p className="font-hand text-sm text-graphite">clearing the desk…</p>
    );
  }

  return (
    <div>
      {/* The counts live in a sentence, not in a row of stat tiles */}
      <header className="max-w-2xl">
        <h1 className="font-hand text-2xl leading-snug">
          {totalDue === 0
            ? "Nothing due — the desk is clear."
            : `${totalDue} card${totalDue === 1 ? "" : "s"} due across ${subjectsWithDue} subject${
                subjectsWithDue === 1 ? "" : "s"
              }.`}
        </h1>
        <p className="mt-2 text-sm text-graphite">
          {profiles.length} subject{profiles.length === 1 ? "" : "s"} in the
          binder, {profiles.reduce((sum, p) => sum + p.card_count, 0)} cards
          written so far.
        </p>

        {totalDue > 0 && (
          <Link
            href="/review"
            className="mt-5 inline-block rounded-md bg-navy px-5 py-2.5 font-hand text-sm text-paper transition-transform hover:-translate-y-0.5"
          >
            Start reviewing →
          </Link>
        )}
      </header>

      <section className="mt-12">
        <h2 className="font-hand text-sm text-graphite">Your subjects</h2>

        {profiles.length === 0 ? (
          <p className="mt-4 text-sm text-graphite">
            Nothing filed yet.{" "}
            <Link
              href="/profiles"
              className="underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
            >
              Start a subject
            </Link>{" "}
            and it&apos;ll get its own colour.
          </p>
        ) : (
          /* Uneven gaps so the row never snaps into a tidy grid */
          <div className="mt-5 flex flex-wrap items-stretch gap-x-7 gap-y-9">
            {profiles.slice(0, 6).map((profile) => (
              <div key={profile.id} className="w-full sm:w-60">
                <FolderCard profile={profile} />
              </div>
            ))}
          </div>
        )}

        {profiles.length > 6 && (
          <Link
            href="/profiles"
            className="mt-8 inline-block font-hand text-sm text-graphite hover:text-ink"
          >
            all {profiles.length} subjects →
          </Link>
        )}
      </section>
    </div>
  );
}
