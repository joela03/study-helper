"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Profile } from "@/types";
import { getProfiles } from "@/lib/api";

interface ProfilesValue {
  profiles: Profile[];
  loading: boolean;
  refresh: () => Promise<void>;
  add: (profile: Profile) => void;
}

const ProfilesContext = createContext<ProfilesValue | null>(null);

/**
 * The subject list is shown in the left rail on every screen as well as on the
 * pages themselves, so it's fetched once here rather than per-page.
 */
export function ProfilesProvider({ children }: { children: React.ReactNode }) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await getProfiles();
      setProfiles(res.profiles);
    } catch (error) {
      console.error("Failed to fetch profiles:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const add = useCallback((profile: Profile) => {
    setProfiles((current) => [...current, profile]);
  }, []);

  return (
    <ProfilesContext.Provider value={{ profiles, loading, refresh, add }}>
      {children}
    </ProfilesContext.Provider>
  );
}

export function useProfiles(): ProfilesValue {
  const value = useContext(ProfilesContext);
  if (!value) {
    throw new Error("useProfiles must be used inside ProfilesProvider");
  }
  return value;
}
