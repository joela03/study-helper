"use client";

import { useState } from "react";
import { createProfile } from "@/lib/api";
import { useProfiles } from "@/lib/profiles-context";
import { ACCENTS } from "@/lib/accents";
import FolderCard from "@/components/FolderCard";

export default function ProfilesPage() {
  const { profiles, loading, add } = useProfiles();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCode, setNewCode] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;

    setCreating(true);
    setError(null);
    try {
      const profile = await createProfile({
        name: newName,
        module_code: newCode || undefined,
      });
      add(profile);
      setNewName("");
      setNewCode("");
      setShowCreate(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create that one");
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return <p className="font-hand text-sm text-graphite">finding them…</p>;
  }

  /* Colours are assigned by id, so the next one is predictable before saving */
  const nextAccent = ACCENTS[profiles.length % ACCENTS.length];

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="font-hand text-2xl">Subjects</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="font-hand text-sm text-graphite underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
        >
          {showCreate ? "never mind" : "+ new subject"}
        </button>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="lift mt-6 max-w-xl rounded-tl-xl rounded-br-xl rounded-bl-sm border border-rule bg-paper p-6"
          style={{ "--rot": "-0.5deg", "--lx": "1.1px" } as React.CSSProperties}
        >
          <div className="flex items-center gap-2">
            <span
              className="h-3.5 w-3.5 rounded-full"
              style={{ backgroundColor: nextAccent.paper }}
              aria-hidden="true"
            />
            <p className="font-hand text-sm text-graphite">
              this one will be {nextAccent.key}
            </p>
          </div>

          {error && (
            <p className="mt-3 text-sm" style={{ color: "#9e4f54" }}>
              {error}
            </p>
          )}

          <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
            <label className="block">
              <span className="font-hand text-xs text-graphite">Name</span>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Machine Learning"
                className="mt-1 w-full border-b border-rule bg-transparent pb-1.5 text-ink placeholder:text-ink/30 focus:border-navy focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="font-hand text-xs text-graphite">
                Module code
              </span>
              <input
                type="text"
                value={newCode}
                onChange={(e) => setNewCode(e.target.value)}
                placeholder="CS101"
                className="mt-1 w-full border-b border-rule bg-transparent pb-1.5 text-ink placeholder:text-ink/30 focus:border-navy focus:outline-none"
              />
            </label>
          </div>

          <button
            type="submit"
            disabled={creating || !newName.trim()}
            className="mt-6 rounded-md bg-navy px-5 py-2 font-hand text-sm text-paper transition-transform hover:-translate-y-0.5 disabled:opacity-40 disabled:hover:translate-y-0"
          >
            {creating ? "filing…" : "Add to binder"}
          </button>
        </form>
      )}

      {profiles.length === 0 ? (
        <p className="mt-8 text-sm text-graphite">
          The binder is empty. Start a subject above.
        </p>
      ) : (
        <div className="mt-10 flex flex-wrap items-stretch gap-x-7 gap-y-9">
          {profiles.map((profile) => (
            <div key={profile.id} className="w-full sm:w-60">
              <FolderCard profile={profile} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
