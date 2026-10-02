/**
 * Per-subject accent colours.
 *
 * Derived from the profile id for now — no colour is stored on the backend.
 * Swapping to a stored `accent_color` column later means changing `accentFor`
 * to read the field and nothing else.
 */

export interface Accent {
  key: string;
  /** Card / folder fill */
  paper: string;
  /** Darker sibling: titles, counts, icon details on that subject's surfaces */
  ink: string;
  /** Mid tone: folder tab, progress fill, borders */
  tab: string;
}

export const ACCENTS: Accent[] = [
  { key: "butter", paper: "#f3e3a3", ink: "#8a6e1e", tab: "#e3cb63" },
  { key: "blush", paper: "#f5cbcd", ink: "#9e4f54", tab: "#eba9ad" },
  { key: "sky", paper: "#cbdff2", ink: "#3e6f9e", tab: "#9cc3e4" },
  { key: "sage", paper: "#cfdfd0", ink: "#4c7254", tab: "#a6c4aa" },
  { key: "clay", paper: "#ebcdb4", ink: "#8e5f3c", tab: "#d9ac86" },
  { key: "periwinkle", paper: "#d3dcf0", ink: "#4f5e96", tab: "#aebce2" },
];

export function accentFor(id: number): Accent {
  const i = ((id % ACCENTS.length) + ACCENTS.length) % ACCENTS.length;
  return ACCENTS[i];
}

/**
 * A small, stable rotation per card so a row of folders never snaps into a
 * perfect grid. Deterministic on id, so cards don't jump between renders.
 */
export function rotationFor(id: number, spread = 1.6): number {
  const h = Math.sin(id * 12.9898) * 43758.5453;
  const unit = (h - Math.floor(h)) * 2 - 1; // -1..1
  return Math.round(unit * spread * 100) / 100;
}

/** Shadow offset, biased opposite the rotation so the lift reads physically. */
export function liftOffsetFor(rotation: number): number {
  return Math.round(rotation * -2.2 * 10) / 10;
}
