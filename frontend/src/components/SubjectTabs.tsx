"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { accentFor } from "@/lib/accents";
import { useProfiles } from "@/lib/profiles-context";

/**
 * The left rail: subjects as the coloured edge tabs of a ring binder. The
 * active subject's tab slides out of the stack and into the page.
 */
export default function SubjectTabs() {
  const pathname = usePathname();
  const params = useParams();
  const { profiles, loading } = useProfiles();

  const activeId = params?.id ? Number(params.id) : null;

  const navLinks = [
    { href: "/", label: "Desk" },
    { href: "/review", label: "Review" },
  ];

  return (
    <nav className="shrink-0 border-b border-rule bg-rule/20 px-4 py-4 lg:w-60 lg:border-r lg:border-b-0 lg:px-0 lg:py-7">
      <Link
        href="/"
        className="block font-hand text-xl leading-none text-ink lg:px-6"
      >
        Study Helper
      </Link>

      <div className="mt-4 flex gap-4 lg:mt-7 lg:flex-col lg:gap-1 lg:px-6">
        {navLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`font-hand text-sm transition-colors ${
              pathname === link.href
                ? "text-ink underline decoration-rule decoration-2 underline-offset-4"
                : "text-graphite hover:text-ink"
            }`}
          >
            {link.label}
          </Link>
        ))}
      </div>

      <p className="mt-6 font-hand text-xs text-graphite lg:mt-9 lg:px-6">
        Subjects
      </p>

      <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1 lg:mt-3 lg:flex-col lg:gap-1 lg:overflow-visible lg:pb-0 lg:pl-4">
        {loading && (
          <span className="font-hand text-xs text-graphite lg:px-2">
            opening the binder…
          </span>
        )}

        {!loading && profiles.length === 0 && (
          <Link
            href="/profiles"
            className="font-hand text-xs text-graphite underline decoration-rule underline-offset-4 hover:text-ink lg:px-2"
          >
            start your first one
          </Link>
        )}

        {profiles.map((profile) => {
          const accent = accentFor(profile.id);
          const isActive = activeId === profile.id;

          return (
            <Link
              key={profile.id}
              href={`/profiles/${profile.id}`}
              style={{
                backgroundColor: accent.paper,
                color: accent.ink,
                borderColor: accent.tab,
              }}
              className={`flex shrink-0 items-center justify-between gap-3 rounded-l-md border-y border-l py-2 pr-3 pl-3 transition-all lg:rounded-r-none ${
                isActive
                  ? "translate-x-0 shadow-[inset_3px_0_0_0_rgb(35_48_58_/_0.35)] lg:-mr-px"
                  : "opacity-80 hover:opacity-100 lg:translate-x-0 lg:hover:translate-x-1"
              }`}
            >
              <span className="truncate font-hand text-sm">{profile.name}</span>
              {profile.due_card_count > 0 && (
                <span
                  className="shrink-0 rounded-full px-1.5 font-hand text-[0.7rem] leading-5"
                  style={{ backgroundColor: accent.tab }}
                >
                  {profile.due_card_count}
                </span>
              )}
            </Link>
          );
        })}
      </div>

      <Link
        href="/profiles"
        className="mt-4 ml-4 hidden font-hand text-xs text-graphite hover:text-ink lg:inline-block"
      >
        + new subject
      </Link>
    </nav>
  );
}
