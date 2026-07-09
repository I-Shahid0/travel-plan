"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { authClient } from "@/lib/auth-client";

/** Shared email/password form for sign-in and sign-up. */
export function AuthForm({ variant }: { variant: "sign-in" | "sign-up" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const nextPath = searchParams.get("next") ?? "/search";
  const isSignUp = variant === "sign-up";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);

    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    const name = String(form.get("name") ?? "");

    const { error: authError } = isSignUp
      ? await authClient.signUp.email({ email, password, name })
      : await authClient.signIn.email({ email, password });

    if (authError) {
      setError(authError.message ?? "Something went adrift — try again.");
      setPending(false);
      return;
    }
    router.push(nextPath);
    router.refresh();
  }

  return (
    <div>
      <p className="voice-etch mb-2">{isSignUp ? "New navigator" : "Welcome back"}</p>
      <h1 className="voice-display text-2xl font-light text-starlight">
        {isSignUp ? (
          <>
            Join the <em className="voice-wonk text-gradient-brass">expedition</em>
          </>
        ) : (
          <>
            Resume your <em className="voice-wonk text-gradient-brass">voyage</em>
          </>
        )}
      </h1>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        {isSignUp && (
          <div>
            <label htmlFor="auth-name" className="voice-etch mb-2 block">
              Name
            </label>
            <input
              id="auth-name"
              name="name"
              type="text"
              required
              autoComplete="name"
              placeholder="Amelia Meridian"
              className="input-field"
            />
          </div>
        )}

        <div>
          <label htmlFor="auth-email" className="voice-etch mb-2 block">
            Email
          </label>
          <input
            id="auth-email"
            name="email"
            type="email"
            required
            autoComplete="email"
            placeholder="you@example.com"
            className="input-field"
          />
        </div>

        <div>
          <label htmlFor="auth-password" className="voice-etch mb-2 block">
            Password
          </label>
          <input
            id="auth-password"
            name="password"
            type="password"
            required
            minLength={8}
            autoComplete={isSignUp ? "new-password" : "current-password"}
            placeholder="eight characters or more"
            className="input-field"
          />
        </div>

        {error && (
          <p role="alert" className="rounded-lg border border-aurora-rose/30 bg-aurora-rose/5 px-4 py-3 text-xs text-aurora-rose">
            {error}
          </p>
        )}

        <button type="submit" disabled={pending} className="btn-brass w-full !py-3.5">
          {pending ? "Aligning…" : isSignUp ? "Begin charting" : "Sign in"}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-faint">
        {isSignUp ? (
          <>
            Already charted?{" "}
            <Link
              href={`/sign-in?next=${encodeURIComponent(nextPath)}`}
              className="text-aurora-teal underline-offset-4 hover:underline"
            >
              Sign in
            </Link>
          </>
        ) : (
          <>
            No account yet?{" "}
            <Link
              href={`/sign-up?next=${encodeURIComponent(nextPath)}`}
              className="text-aurora-teal underline-offset-4 hover:underline"
            >
              Join the expedition
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
