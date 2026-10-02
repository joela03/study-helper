/**
 * The blank / dot / grid paper choice, persisted in localStorage.
 *
 * Applied as a `data-paper` attribute on <html> by an inline script in the
 * root layout, so the right surface is painted before React hydrates rather
 * than flashing the default first. See the Next.js guide "Preventing flash
 * before hydration" — the script and the lazy useState initializer in
 * PaperToggle must read from the same place so they always agree.
 */

export type PaperMode = "blank" | "dot" | "grid";

export const PAPER_MODES: PaperMode[] = ["blank", "dot", "grid"];

export const PAPER_STORAGE_KEY = "study-helper:paper";
export const DEFAULT_PAPER: PaperMode = "dot";

/** Runs in <head> during HTML parsing, before first paint. */
export const PAPER_INLINE_SCRIPT = `(function(){try{var p=localStorage.getItem(${JSON.stringify(
  PAPER_STORAGE_KEY
)});if(${JSON.stringify(
  PAPER_MODES
)}.indexOf(p)>-1)document.documentElement.setAttribute("data-paper",p)}catch(e){}})()`;

export function readPaper(): PaperMode {
  if (typeof window === "undefined") return DEFAULT_PAPER;
  try {
    const saved = window.localStorage.getItem(PAPER_STORAGE_KEY);
    if (saved && (PAPER_MODES as string[]).includes(saved)) {
      return saved as PaperMode;
    }
  } catch {
    // Private browsing or blocked storage — the default surface is fine.
  }
  return DEFAULT_PAPER;
}

export function writePaper(mode: PaperMode): void {
  try {
    window.localStorage.setItem(PAPER_STORAGE_KEY, mode);
  } catch {
    // Not worth surfacing; the choice just won't persist.
  }
  document.documentElement.setAttribute("data-paper", mode);
}
