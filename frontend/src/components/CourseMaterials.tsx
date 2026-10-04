"use client";

import { useCallback, useEffect, useState } from "react";
import { CourseMaterial, MaterialKind } from "@/types";
import { Accent } from "@/lib/accents";
import {
  createMaterial,
  deleteMaterial,
  getMaterials,
  updateMaterial,
} from "@/lib/api";

interface Props {
  profileId: number;
  accent: Accent;
}

const KINDS: { key: MaterialKind; label: string }[] = [
  { key: "outline", label: "course outline" },
  { key: "past_paper", label: "past paper" },
  { key: "problem_sheet", label: "problem sheet" },
  { key: "notes", label: "notes" },
  { key: "other", label: "other" },
];

const ACCEPT = ".pdf,.pptx,.ppt,.docx,.txt,.md";

function kindLabel(kind: MaterialKind): string {
  return KINDS.find((k) => k.key === kind)?.label ?? kind;
}

/**
 * Everything about a subject that isn't a lecture. Added when the subject
 * starts and topped up as more papers appear, so each one stays editable.
 */
export default function CourseMaterials({ profileId, accent }: Props) {
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<MaterialKind>("past_paper");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const [draftTitle, setDraftTitle] = useState("");
  const [draftContent, setDraftContent] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await getMaterials(profileId);
      setMaterials(res.materials);
    } catch (err) {
      console.error("Failed to fetch materials:", err);
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    load();
  }, [load]);

  function resetForm() {
    setTitle("");
    setText("");
    setFile(null);
    setKind("past_paper");
    setAdding(false);
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setError("Give it a title");
      return;
    }
    if (!file && !text.trim()) {
      setError("Attach a file or type something in");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await createMaterial({
        profileId,
        title: title.trim(),
        kind,
        content: text.trim() || undefined,
        file: file || undefined,
      });
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add that");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(material: CourseMaterial) {
    setEditing(material.id);
    setDraftTitle(material.title);
    setDraftContent(material.content ?? "");
    setError(null);
  }

  async function saveEdit(id: number) {
    setBusy(true);
    try {
      await updateMaterial(id, { title: draftTitle, content: draftContent });
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: number) {
    setBusy(true);
    try {
      await deleteMaterial(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove it");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="font-hand text-sm text-graphite">checking the folder…</p>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-sm text-graphite">
          {materials.length === 0
            ? "Nothing filed yet — the outline and any past papers sharpen how concepts get written."
            : `${materials.length} item${materials.length === 1 ? "" : "s"} shaping how this subject is condensed.`}
        </p>
        <button
          onClick={() => setAdding(!adding)}
          className="font-hand text-xs text-graphite underline decoration-rule decoration-2 underline-offset-4 hover:text-ink"
        >
          {adding ? "never mind" : "+ add material"}
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-[#9e4f54]">{error}</p>}

      {adding && (
        <form
          onSubmit={handleAdd}
          className="mt-4 rounded-tl-xl rounded-br-xl rounded-bl-sm border border-dashed p-4"
          style={{ borderColor: accent.tab }}
        >
          <div className="flex flex-wrap gap-1.5">
            {KINDS.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setKind(option.key)}
                className="rounded-md px-2.5 py-1 font-hand text-xs transition-colors"
                style={
                  kind === option.key
                    ? { backgroundColor: accent.tab, color: accent.ink }
                    : { color: "var(--color-graphite)" }
                }
              >
                {option.label}
              </button>
            ))}
          </div>

          <label className="mt-3 block">
            <span className="font-hand text-xs text-graphite">Title</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. 2023-24 exam paper"
              className="mt-1 w-full border-b border-rule bg-transparent pb-1.5 text-ink placeholder:text-ink/30 focus:border-navy focus:outline-none"
            />
          </label>

          <label className="mt-3 block">
            <span className="font-hand text-xs text-graphite">
              File — pdf, pptx, docx, txt, md
            </span>
            <input
              type="file"
              accept={ACCEPT}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="mt-1 w-full text-sm text-graphite file:mr-3 file:rounded file:border-0 file:bg-rule/50 file:px-3 file:py-1.5 file:font-sans file:text-ink hover:file:bg-rule"
            />
          </label>

          <label className="mt-3 block">
            <span className="font-hand text-xs text-graphite">
              …or type it in
            </span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              placeholder="Module outline, assessment format, anything worth knowing"
              className="mt-1 w-full resize-y border-b border-rule bg-transparent pb-1.5 text-sm leading-6 text-ink placeholder:text-ink/30 focus:border-navy focus:outline-none"
            />
          </label>

          <button
            type="submit"
            disabled={busy}
            className="mt-4 rounded-md px-4 py-2 font-hand text-sm transition-transform hover:-translate-y-0.5 disabled:opacity-50"
            style={{ backgroundColor: accent.tab, color: accent.ink }}
          >
            {busy ? "filing…" : "File it"}
          </button>
        </form>
      )}

      {materials.length > 0 && (
        <ul className="mt-4 divide-y divide-rule">
          {materials.map((material) => (
            <li key={material.id} className="py-3">
              {editing === material.id ? (
                <div>
                  <input
                    type="text"
                    value={draftTitle}
                    onChange={(e) => setDraftTitle(e.target.value)}
                    className="w-full border-b border-rule bg-transparent pb-1 text-sm text-ink focus:border-navy focus:outline-none"
                  />
                  <textarea
                    value={draftContent}
                    onChange={(e) => setDraftContent(e.target.value)}
                    rows={6}
                    className="mt-2 w-full resize-y border border-rule bg-transparent p-2 text-sm leading-6 text-ink focus:border-navy focus:outline-none"
                  />
                  <div className="mt-2 flex gap-3">
                    <button
                      onClick={() => saveEdit(material.id)}
                      disabled={busy}
                      className="font-hand text-xs disabled:opacity-50"
                      style={{ color: accent.ink }}
                    >
                      save
                    </button>
                    <button
                      onClick={() => setEditing(null)}
                      className="font-hand text-xs text-graphite hover:text-ink"
                    >
                      cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-ink">{material.title}</p>
                    <p className="mt-0.5 text-xs text-ink/45">
                      <span style={{ color: accent.ink }}>
                        {kindLabel(material.kind)}
                      </span>
                      {" · "}
                      {material.content_chars.toLocaleString()} chars
                      {material.file_path ? " · from file" : " · typed in"}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-3">
                    <button
                      onClick={() => startEdit(material)}
                      className="font-hand text-xs text-graphite hover:text-ink"
                    >
                      edit
                    </button>
                    <button
                      onClick={() => handleDelete(material.id)}
                      disabled={busy}
                      className="font-hand text-xs text-graphite hover:text-[#9e4f54] disabled:opacity-50"
                    >
                      remove
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
