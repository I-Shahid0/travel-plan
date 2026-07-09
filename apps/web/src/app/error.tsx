"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[app]", error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[70svh] max-w-xl flex-col items-center justify-center px-5 pt-24 text-center">
      <span aria-hidden="true" className="text-4xl text-aurora-rose/70">
        ☄
      </span>
      <h1 className="voice-display mt-6 text-3xl font-light text-starlight">
        A disturbance in the <em className="voice-wonk text-gradient-aurora">sky</em>
      </h1>
      <p className="mt-4 max-w-sm text-sm leading-relaxed text-dim">
        Something unexpected interrupted the observation. The instruments are intact — try again.
      </p>
      <button type="button" onClick={reset} className="btn-brass mt-8">
        Realign
      </button>
    </div>
  );
}
