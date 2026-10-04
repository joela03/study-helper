/**
 * Access token storage.
 *
 * localStorage rather than a cookie because the API is a separate origin and
 * the token is sent as a bearer header. Every read is guarded: storage can
 * throw in private browsing.
 */
const TOKEN_KEY = "study-helper:token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Not fatal — the session just won't survive a reload
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to do
  }
}
