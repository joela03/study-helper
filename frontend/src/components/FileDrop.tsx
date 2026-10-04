"use client";

import { useRef, useState } from "react";

interface Props {
  accept: string;
  /** Rendered inside the zone when nothing is held. */
  hint: string;
  /** Name of the currently held file, if any. */
  filename?: string | null;
  /** One line about what will happen to it. */
  note?: string | null;
  tone: string;
  onFile: (file: File) => void;
  onClear?: () => void;
}

/** A drop zone that also opens the file picker when clicked. */
export default function FileDrop({
  accept,
  hint,
  filename,
  note,
  tone,
  onFile,
  onClear,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onFile(file);
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className="cursor-pointer rounded-md border border-dashed px-4 py-6 text-center transition-colors"
        style={{
          borderColor: over ? tone : "var(--color-rule)",
          backgroundColor: over ? `${tone}33` : "transparent",
        }}
      >
        {filename ? (
          <p className="truncate text-sm text-ink">{filename}</p>
        ) : (
          <p className="font-hand text-sm text-graphite">{hint}</p>
        )}
        <p className="mt-1 text-xs text-ink/40">
          {filename ? note : "drop it here, or click to browse"}
        </p>
      </div>

      {filename && onClear && (
        <button
          type="button"
          onClick={onClear}
          className="mt-1.5 font-hand text-xs text-graphite hover:text-ink"
        >
          take it back off
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          // Reset so re-picking the same file still fires a change
          e.target.value = "";
        }}
      />
    </div>
  );
}
