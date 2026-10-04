"use client";

import { useState } from "react";
import { login, register } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

type Mode = "signin" | "signup";

export default function LoginPage() {
  const { signIn } = useAuth();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "signin"
          ? await login(email, password)
          : await register({ email, display_name: name, password });
      signIn(result.access_token, result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="canvas flex min-h-dvh items-center justify-center px-5">
      <div
        className="lift w-full max-w-sm"
        style={{ "--rot": "-0.7deg", "--lx": "1.5px" } as React.CSSProperties}
      >
        <div className="overflow-hidden rounded-tl-xl rounded-br-xl rounded-bl-sm">
          <form
            onSubmit={handleSubmit}
            className="folded relative bg-[#f3e3a3] p-7"
          >
            <h1 className="font-hand text-xl text-[#8a6e1e]">
              {mode === "signin" ? "Open your binder" : "Start a binder"}
            </h1>
            <p className="mt-1 text-sm text-ink/60">
              {mode === "signin"
                ? "Sign in to pick up where you left off."
                : "Your subjects and review history stay yours."}
            </p>

            {error && <p className="mt-3 text-sm text-[#9e4f54]">{error}</p>}

            {mode === "signup" && (
              <label className="mt-5 block">
                <span className="font-hand text-xs text-ink/60">Name</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="mt-1 w-full border-b border-[#8a6e1e]/30 bg-transparent pb-1.5 text-ink focus:border-[#8a6e1e] focus:outline-none"
                />
              </label>
            )}

            <label className="mt-4 block">
              <span className="font-hand text-xs text-ink/60">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="mt-1 w-full border-b border-[#8a6e1e]/30 bg-transparent pb-1.5 text-ink focus:border-[#8a6e1e] focus:outline-none"
              />
            </label>

            <label className="mt-4 block">
              <span className="font-hand text-xs text-ink/60">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete={
                  mode === "signin" ? "current-password" : "new-password"
                }
                className="mt-1 w-full border-b border-[#8a6e1e]/30 bg-transparent pb-1.5 text-ink focus:border-[#8a6e1e] focus:outline-none"
              />
            </label>

            <button
              type="submit"
              disabled={busy}
              className="mt-6 w-full rounded-md bg-navy py-2.5 font-hand text-sm text-paper transition-transform hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0"
            >
              {busy
                ? "just a moment…"
                : mode === "signin"
                  ? "Sign in"
                  : "Create account"}
            </button>

            <button
              type="button"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError(null);
              }}
              className="mt-4 w-full font-hand text-xs text-ink/55 hover:text-ink"
            >
              {mode === "signin"
                ? "no account yet? start one"
                : "already have one? sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
