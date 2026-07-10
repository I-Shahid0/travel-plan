"use client";

import { useState, useTransition } from "react";

import { clearHistory } from "@/app/history/actions";

/** Two-step destructive action: first click arms it, second click erases. */
export function ClearHistoryButton() {
  const [armed, setArmed] = useState(false);
  const [pending, startTransition] = useTransition();

  if (!armed) {
    return (
      <button type="button" onClick={() => setArmed(true)} className="btn-ghost !text-aurora-rose">
        Erase history
      </button>
    );
  }

  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        disabled={pending}
        onClick={() =>
          startTransition(async () => {
            await clearHistory();
            setArmed(false);
          })
        }
        className="btn-ghost !border-aurora-rose/50 !text-aurora-rose"
      >
        {pending ? "Erasing…" : "Really erase everything"}
      </button>
      <button
        type="button"
        disabled={pending}
        onClick={() => setArmed(false)}
        className="btn-ghost"
      >
        Keep it
      </button>
    </span>
  );
}
