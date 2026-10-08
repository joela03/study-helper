"use client";

import { useMemo } from "react";
import katex from "katex";

interface Props {
  children: string;
  className?: string;
}

/**
 * Renders text containing LaTeX between dollar signs.
 *
 * The model is asked to write maths as $inline$ or $$display$$, which
 * otherwise reaches the page as literal dollar signs and backslashes —
 * "$F(u,v) = \sum_x f(x,y)$" is unreadable as plain text.
 *
 * Splitting on delimiters rather than rendering the whole string keeps the
 * prose as prose: KaTeX would otherwise need the whole paragraph to be
 * valid LaTeX.
 */
function splitOnMaths(text: string): { maths: boolean; display: boolean; body: string }[] {
  // $$...$$ first, so the display form isn't eaten by the inline pattern
  const pattern = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;
  const pieces: { maths: boolean; display: boolean; body: string }[] = [];

  let lastIndex = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      pieces.push({ maths: false, display: false, body: text.slice(lastIndex, start) });
    }
    const raw = match[0];
    const display = raw.startsWith("$$");
    pieces.push({
      maths: true,
      display,
      body: display ? raw.slice(2, -2) : raw.slice(1, -1),
    });
    lastIndex = start + raw.length;
  }

  if (lastIndex < text.length) {
    pieces.push({ maths: false, display: false, body: text.slice(lastIndex) });
  }

  return pieces;
}

export default function Maths({ children, className }: Props) {
  const pieces = useMemo(() => splitOnMaths(children ?? ""), [children]);

  return (
    <span className={className}>
      {pieces.map((piece, i) => {
        if (!piece.maths) return <span key={i}>{piece.body}</span>;

        let html: string;
        try {
          html = katex.renderToString(piece.body, {
            displayMode: piece.display,
            throwOnError: false,
            // Malformed LaTeX shows in context rather than blowing up the page
            errorColor: "#9e4f54",
            output: "html",
          });
        } catch {
          // Anything KaTeX can't parse at all falls back to the source
          return <code key={i}>{piece.body}</code>;
        }

        return (
          <span
            key={i}
            className={piece.display ? "my-2 block overflow-x-auto" : undefined}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      })}
    </span>
  );
}
