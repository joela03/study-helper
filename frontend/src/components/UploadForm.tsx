"use client";

import { useState } from "react";
import { uploadTranscript } from "@/lib/api";
import { Transcript } from "@/types";
import { Accent } from "@/lib/accents";

interface Props {
  profileId: number;
  accent: Accent;
  onUploaded: (transcript: Transcript) => void;
}

export default function UploadForm({ profileId, accent, onUploaded }: Props) {
  const [title, setTitle] = useState("");
  const [document, setDocument] = useState<File | null>(null);
  const [audio, setAudio] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Give it a title first");
      return;
    }
    if (!document && !audio) {
      setError("Attach a document or an audio file");
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const transcript = await uploadTranscript(
        profileId,
        title,
        document || undefined,
        audio || undefined
      );
      onUploaded(transcript);
      setTitle("");
      setDocument(null);
      setAudio(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const fileInput =
    "mt-1 w-full text-sm text-graphite file:mr-3 file:rounded file:border-0 file:bg-rule/50 file:px-3 file:py-1.5 file:font-sans file:text-ink hover:file:bg-rule";

  return (
    <form
      onSubmit={handleSubmit}
      className="lift rounded-tl-xl rounded-br-xl rounded-bl-sm border border-dashed p-5"
      style={
        {
          "--rot": "0.4deg",
          "--lx": "-0.9px",
          borderColor: accent.tab,
        } as React.CSSProperties
      }
    >
      <h3 className="font-hand text-sm" style={{ color: accent.ink }}>
        Add a lecture
      </h3>

      {error && (
        <p className="mt-2 text-sm text-[#9e4f54]">{error}</p>
      )}

      <div className="mt-4 space-y-4">
        <label className="block">
          <span className="font-hand text-xs text-graphite">Title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Lecture 1 — Introduction"
            className="mt-1 w-full border-b border-rule bg-transparent pb-1.5 text-ink placeholder:text-ink/30 focus:border-navy focus:outline-none"
          />
        </label>

        <label className="block">
          <span className="font-hand text-xs text-graphite">
            Document — pdf, pptx, txt
          </span>
          <input
            type="file"
            accept=".pdf,.pptx,.ppt,.txt"
            onChange={(e) => setDocument(e.target.files?.[0] || null)}
            className={fileInput}
          />
        </label>

        <label className="block">
          <span className="font-hand text-xs text-graphite">
            Audio — mp3, wav, m4a
          </span>
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac"
            onChange={(e) => setAudio(e.target.files?.[0] || null)}
            className={fileInput}
          />
        </label>

        <button
          type="submit"
          disabled={isUploading}
          className="rounded-md px-4 py-2 font-hand text-sm transition-transform hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0"
          style={{ backgroundColor: accent.tab, color: accent.ink }}
        >
          {isUploading ? "filing…" : "File it"}
        </button>
      </div>
    </form>
  );
}
