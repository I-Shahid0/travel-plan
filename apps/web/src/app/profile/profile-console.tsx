"use client";

import { useActionState, useRef } from "react";

import { linkYelpProfile, type ProfileState } from "@/app/profile/actions";
import { DEMO_PERSONAS } from "@/lib/personas";

const initialProfileState: ProfileState = { status: "idle", message: null };

/**
 * Links a Better Auth account to a Yelp interaction user id — the bridge
 * that turns personalization on. Demo personas fill the field one click.
 */
export function ProfileConsole({ currentYelpUserId }: { currentYelpUserId: string | null }) {
  const [state, formAction, pending] = useActionState(linkYelpProfile, initialProfileState);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-8">
      <section className="panel-etched hairline-aurora p-6 sm:p-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h2 className="voice-etch !text-aurora-violet">Personal sky</h2>
          {currentYelpUserId ? (
            <span className="chip !border-aurora-teal/40 !text-aurora-teal">
              ◉ linked · {currentYelpUserId.slice(0, 12)}…
            </span>
          ) : (
            <span className="chip">○ not linked</span>
          )}
        </header>

        <p className="max-w-xl text-sm leading-relaxed text-dim">
          Meridian&apos;s personalization speaks the Yelp Open Dataset&apos;s language: link a
          traveler id from the interaction history and every search and journey bends toward that
          taste. Your account identity stays separate — this is a lens, not a name change.
        </p>

        <form action={formAction} className="mt-7 flex flex-col gap-3 sm:flex-row">
          <input
            ref={inputRef}
            type="text"
            name="yelpUserId"
            defaultValue={currentYelpUserId ?? ""}
            placeholder="Yelp user id, e.g. fCvMnJU1Z-XhAjKg99wK3Q"
            className="input-field font-mono !text-sm"
            aria-label="Yelp user id"
          />
          <button type="submit" disabled={pending} className="btn-brass shrink-0">
            {pending ? "Aligning…" : "Link profile"}
          </button>
        </form>

        {state.status !== "idle" && state.message && (
          <p
            role="status"
            className={`mt-4 text-xs ${state.status === "ok" ? "text-aurora-teal" : "text-aurora-rose"}`}
          >
            {state.message}
          </p>
        )}

        {currentYelpUserId && (
          <form action={formAction} className="mt-3">
            <input type="hidden" name="yelpUserId" value="" />
            <button
              type="submit"
              disabled={pending}
              className="cursor-pointer font-mono text-[0.6875rem] tracking-[0.1em] text-faint uppercase underline-offset-4 transition-colors hover:text-aurora-rose hover:underline"
            >
              Unlink and return to the shared sky
            </button>
          </form>
        )}
      </section>

      <section>
        <p className="voice-etch mb-4">Borrow a traveler&apos;s eyes</p>
        <div className="grid gap-4 sm:grid-cols-2">
          {DEMO_PERSONAS.map((persona) => {
            const active = persona.yelpUserId === currentYelpUserId;
            return (
              <button
                key={persona.yelpUserId}
                type="button"
                onClick={() => {
                  if (inputRef.current) {
                    inputRef.current.value = persona.yelpUserId;
                    inputRef.current.focus();
                    inputRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
                  }
                }}
                className={`panel group cursor-pointer p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-(--line-bright) ${
                  active ? "!border-aurora-teal/50" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <h3 className="voice-display text-lg text-starlight">{persona.name}</h3>
                  {active && (
                    <span aria-hidden="true" className="text-aurora-teal">
                      ◉
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-dim italic">{persona.flavor}</p>
                <p className="mt-3 font-mono text-[0.625rem] tracking-[0.1em] text-faint">
                  {persona.interactions.toLocaleString()} interactions ·{" "}
                  {persona.yelpUserId.slice(0, 14)}…
                </p>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
