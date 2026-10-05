"use client";

import { useState } from "react";
import { uploadTranscript } from "@/lib/api";
import { Transcript } from "@/types";
import { Accent } from "@/lib/accents";
import FileDrop from "@/components/FileDrop";
import {
  LECTURE_ACCEPT,
  LectureFileKind,
  classifyLectureFile,
  describeLectureFile,
} from "@/lib/lecture-files";

interface Props {
  profileId: number;
  accent: Accent;
  onUploaded: (transcript: Transcript) => void;
}

export default function UploadForm({ profileId, accent, onUploaded }: Props) {
  const [title, setTitle] = useState("");
  const [document, setDocument] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [lectureFile, setLectureFile] = useState<File | null>(null);
  const [lectureKind, setLectureKind] = useState<LectureFileKind | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pasted = text.trim();

  function clearLectureFile() {
    setLectureFile(null);
    setLectureKind(null);
  }

  /**
   * Both drop zones funnel through here. The kind decides what happens:
   * plain text is read straight into the box so it can be checked and
   * edited, Word is held as a file for the server to open, and anything
   * else is treated as a recording.
   */
  async function handleFile(file: File) {
    const kind = classifyLectureFile(file);
    setError(null);

    if (kind === "legacy-word") {
      clearLectureFile();
      setError(describeLectureFile(kind));
      return;
    }

    if (kind === "audio") {
      clearLectureFile();
      setError(describeLectureFile(kind));
      return;
    }

    if (kind === "text") {
      try {
        const content = await file.text();
        setText(content);
        clearLectureFile();
      } catch {
        setError("Couldn't read that file");
      }
      return;
    }

    setLectureFile(file);
    setLectureKind(kind);
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Give it a title first");
      return;
    }

    const sendingDoc = lectureKind === "word" ? lectureFile : null;
    const sendingText = sendingDoc ? "" : pasted;

    if (!document && !sendingDoc && !sendingText) {
      setError("Add slides, paste a transcript, or drop a file in");
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const transcript = await uploadTranscript({
        profileId,
        title,
        document: document || undefined,
        transcriptFile: sendingDoc || undefined,
        transcriptText: sendingText || undefined,
      });
      onUploaded(transcript);
      setTitle("");
      setDocument(null);
      setText("");
      clearLectureFile();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

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

      {error && <p className="mt-2 text-sm text-[#9e4f54]">{error}</p>}

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
            Slides — pdf, pptx, txt (optional)
          </span>
          <input
            type="file"
            accept=".pdf,.pptx,.ppt,.txt,.docx"
            onChange={(e) => setDocument(e.target.files?.[0] || null)}
            className="mt-1 w-full text-sm text-graphite file:mr-3 file:rounded file:border-0 file:bg-rule/50 file:px-3 file:py-1.5 file:font-sans file:text-ink hover:file:bg-rule"
          />
        </label>

        {/* The lecture's spoken content, already transcribed */}
        <div>
          <p className="font-hand text-xs text-graphite">Transcript</p>

          <div
            className="mt-2 space-y-3 rounded-md border p-3"
            style={{ borderColor: accent.tab }}
          >
            {lectureKind === "word" && lectureFile ? (
              <FileDrop
                accept={LECTURE_ACCEPT}
                tone={accent.tab}
                hint="drop a transcript in"
                filename={lectureFile.name}
                note={describeLectureFile(lectureKind)}
                onFile={handleFile}
                onClear={clearLectureFile}
              />
            ) : (
              <>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={7}
                  placeholder="Paste the transcript from Panopto here…"
                  className="w-full resize-y bg-transparent text-sm leading-6 text-ink placeholder:text-ink/30 focus:outline-none"
                />
                <p className="text-right text-xs text-ink/40">
                  {pasted
                    ? `${pasted.length.toLocaleString()} characters`
                    : "goes straight to chunking — no transcription step"}
                </p>
                <FileDrop
                  accept={LECTURE_ACCEPT}
                  tone={accent.tab}
                  hint="or drop a .txt, .md or .docx in"
                  onFile={handleFile}
                />
              </>
            )}
          </div>
        </div>

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
