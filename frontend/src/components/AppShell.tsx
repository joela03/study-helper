"use client";

import SubjectTabs from "@/components/SubjectTabs";
import PaperToggle from "@/components/PaperToggle";
import { ProfilesProvider } from "@/lib/profiles-context";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ProfilesProvider>
      <div className="flex min-h-dvh flex-col lg:flex-row">
        <SubjectTabs />
        <main className="canvas flex-1 px-5 py-8 sm:px-10 lg:px-14 lg:py-12">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
      </div>
      <PaperToggle />
    </ProfilesProvider>
  );
}
