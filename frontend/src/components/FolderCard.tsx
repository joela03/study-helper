import Link from "next/link";
import { Profile } from "@/types";
import { accentFor, rotationFor, liftOffsetFor } from "@/lib/accents";

interface Props {
  profile: Profile;
}

/** The folder tab icon — a small closed folder in the subject's darker tone. */
function FolderMark({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7" aria-hidden="true">
      <path
        d="M3 6.6c0-.9.7-1.6 1.6-1.6h4.3c.5 0 1 .25 1.3.67l.9 1.23h8.3c.9 0 1.6.7 1.6 1.6v9.3c0 .9-.7 1.6-1.6 1.6H4.6c-.9 0-1.6-.7-1.6-1.6V6.6Z"
        fill={color}
      />
      <path
        d="M3 9.4h18"
        stroke="rgb(250 246 239 / 0.55)"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function FolderCard({ profile }: Props) {
  const accent = accentFor(profile.id);
  const rotation = rotationFor(profile.id);

  return (
    <Link
      href={`/profiles/${profile.id}`}
      className="lift lift-hover block"
      style={
        {
          "--rot": `${rotation}deg`,
          "--lx": `${liftOffsetFor(rotation)}px`,
        } as React.CSSProperties
      }
    >
      {/* Radii live out here: clip-path on the inner element would override them */}
      <div className="h-full overflow-hidden rounded-tl-xl rounded-br-xl rounded-bl-sm">
        <div
          className="folded relative h-full p-5"
          style={{ backgroundColor: accent.paper }}
        >
          <FolderMark color={accent.ink} />

          <h3
            className="mt-3 font-hand text-lg leading-snug"
            style={{ color: accent.ink }}
          >
            {profile.name}
          </h3>

          {profile.module_code && (
            <p className="mt-0.5 text-sm text-ink/55">{profile.module_code}</p>
          )}

          <div className="mt-4 flex items-center gap-3 text-xs text-ink/60">
            <span>{profile.transcript_count} transcripts</span>
            <span aria-hidden="true">·</span>
            <span>{profile.card_count} cards</span>
          </div>

          {profile.due_card_count > 0 && (
            <p className="mt-2 font-hand text-sm" style={{ color: accent.ink }}>
              {profile.due_card_count} due today
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}
