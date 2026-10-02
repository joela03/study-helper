"use client";

import { useLayoutEffect, useState } from "react";
import {
  PaperMode,
  PAPER_MODES,
  readPaper,
  writePaper,
} from "@/lib/paper-store";

/**
 * The planner's blank / dot / grid tabs, sitting on the desk at the bottom
 * right of the page.
 */
export default function PaperToggle() {
  // Reads the same source as the inline script, so initial state matches the DOM
  const [mode, setMode] = useState<PaperMode>(readPaper);

  // React clears <html> attributes on the dev Strict Mode remount; no-op in prod
  useLayoutEffect(() => {
    document.documentElement.setAttribute("data-paper", readPaper());
  }, []);

  function handleChange(next: PaperMode) {
    setMode(next);
    writePaper(next);
  }

  return (
    <div className="fixed right-5 bottom-5 z-20 flex overflow-hidden rounded-md border border-rule bg-paper/90 backdrop-blur-sm">
      {PAPER_MODES.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => handleChange(option)}
          aria-pressed={mode === option}
          className={`px-3.5 py-1.5 font-hand text-xs transition-colors ${
            mode === option
              ? "bg-navy text-paper"
              : "text-graphite hover:bg-rule/40"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
