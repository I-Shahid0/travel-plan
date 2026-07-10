"use client";

import { useEffect } from "react";

export default function BrowseError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[browse]", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-7xl px-5 pt-28 pb-16">
      <div className="panel-etched mx-auto flex max-w-xl flex-col items-center gap-5 px-8 py-20 text-center">
        <span aria-hidden="true" className="text-3xl text-aurora-rose/70">
          ☄
        </span>
        <h1 className="voice-display text-2xl text-starlight">The atlas stuck shut</h1>
        <p className="max-w-sm text-sm leading-relaxed text-dim">
          The retrieval engine couldn&apos;t open this page of the atlas. It may be waking up —
          try once more.
        </p>
        <p className="font-mono text-xs break-all text-faint">
          {error.message || "unknown disturbance"}
        </p>
        <button type="button" onClick={reset} className="btn-brass mt-2">
          Reopen
        </button>
      </div>
    </div>
  );
}
