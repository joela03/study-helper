"use client";

import { usePathname } from "next/navigation";
import SubjectTabs from "@/components/SubjectTabs";
import PaperToggle from "@/components/PaperToggle";
import { ProfilesProvider } from "@/lib/profiles-context";
import { AuthProvider, useAuth } from "@/lib/auth-context";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  // The login page has no binder around it, and nothing else renders until
  // we know who is asking — otherwise every panel fires a doomed request
  if (pathname === "/login") return <>{children}</>;

  if (loading || !user) {
    return (
      <div className="canvas flex min-h-dvh items-center justify-center">
        <p className="font-hand text-sm text-graphite">finding your binder…</p>
      </div>
    );
  }

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
