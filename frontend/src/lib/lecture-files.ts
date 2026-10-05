/**
 * What a dropped lecture file actually is.
 *
 * Mirrors the suffix sets in backend/app/services/extraction.py. The backend
 * re-checks and re-routes on its own, so this is for telling the user what
 * will happen before they submit, not the authority on it.
 */

export type LectureFileKind = "text" | "word" | "legacy-word" | "audio";

const PLAIN_TEXT = ["txt", "md", "markdown"];
const WORD = ["docx"];
const LEGACY_WORD = ["doc"];

/**
 * Transcript formats only. Audio transcription is off — lectures normally
 * come with a transcript already, and Whisper was the single largest thing
 * the worker loaded. Audio files are still classified so dropping one gets
 * an explanation rather than silent rejection by the picker.
 */
export const LECTURE_ACCEPT = ".txt,.md,.markdown,.docx";

function suffixOf(name: string): string {
  const parts = name.toLowerCase().split(".");
  return parts.length > 1 ? parts[parts.length - 1] : "";
}

export function classifyLectureFile(file: File): LectureFileKind {
  const suffix = suffixOf(file.name);
  if (PLAIN_TEXT.includes(suffix)) return "text";
  if (WORD.includes(suffix)) return "word";
  if (LEGACY_WORD.includes(suffix)) return "legacy-word";
  return "audio";
}

/** One line explaining what we'll do with it, shown under the drop zone. */
export function describeLectureFile(kind: LectureFileKind): string {
  switch (kind) {
    case "text":
      return "already a transcript — no transcription needed";
    case "word":
      return "already a transcript — text pulled out on the server";
    case "legacy-word":
      return "legacy .doc can't be read — save it as .docx or .txt";
    case "audio":
      return "audio transcription is off — paste the transcript, or upload it as .txt, .md or .docx";
  }
}
