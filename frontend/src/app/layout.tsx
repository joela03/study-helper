import type { Metadata } from "next";
import { Karla, Shantell_Sans } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { DEFAULT_PAPER, PAPER_INLINE_SCRIPT } from "@/lib/paper-store";

/** Body copy: questions, answers, transcripts, anything longer than a label. */
const karla = Karla({
  variable: "--font-karla",
  subsets: ["latin"],
});

/** Accent only: folder titles, section headers, tab labels, small notes. */
const shantell = Shantell_Sans({
  variable: "--font-shantell",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Study Helper",
  description: "AI-powered study tool with spaced repetition",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-paper={DEFAULT_PAPER}
      suppressHydrationWarning
      className={`${karla.variable} ${shantell.variable} h-full antialiased`}
    >
      <head>
        {/* Applies the saved paper surface during parsing, before first paint */}
        <script dangerouslySetInnerHTML={{ __html: PAPER_INLINE_SCRIPT }} />
      </head>
      <body className="min-h-full bg-paper font-sans text-ink">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
