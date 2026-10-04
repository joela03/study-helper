"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import { AUTH_EXPIRED_EVENT, AuthUser, getMe } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/auth-store";

interface AuthValue {
  user: AuthUser | null;
  loading: boolean;
  signIn: (token: string, user: AuthUser) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const restore = useCallback(async () => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    try {
      setUser(await getMe());
    } catch {
      // Expired or revoked; the api client has already cleared it
      clearToken();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    restore();
  }, [restore]);

  // A 401 from any request means the session is over
  useEffect(() => {
    function onExpired() {
      setUser(null);
      router.replace("/login");
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [router]);

  // Anything other than the login page needs an account
  useEffect(() => {
    if (loading || pathname === "/login") return;
    if (!user) router.replace("/login");
  }, [loading, user, pathname, router]);

  const signIn = useCallback(
    (token: string, nextUser: AuthUser) => {
      setToken(token);
      setUser(nextUser);
      router.replace("/");
    },
    [router]
  );

  const signOut = useCallback(() => {
    clearToken();
    setUser(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
