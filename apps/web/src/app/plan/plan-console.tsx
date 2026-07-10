"use client";

import { useActionState } from "react";

import { planTrip, type PlanState } from "@/app/plan/actions";
import { ItineraryView } from "@/components/itinerary-view";

const initialPlanState: PlanState = { status: "idle", itinerary: null, error: null };

const JOURNEY_IDEAS = [
  "weekend food tour in Philadelphia",
  "two slow days of coffee and bookstores in Santa Barbara",
  "a night of live music and late food in New Orleans",
];

export function PlanConsole({
  personalized,
  initialQuery = "",
}: {
  personalized: boolean;
  initialQuery?: string;
}) {
  const [state, formAction, pending] = useActionState(planTrip, initialPlanState);

  return (
    <div className="space-y-10">
      <form action={formAction} className="panel-etched hairline-aurora p-6 sm:p-8">
        <div className="grid gap-6 sm:grid-cols-[1fr_auto_auto] sm:items-end">
          <div>
            <label htmlFor="plan-query" className="voice-etch mb-2.5 block">
              The journey
            </label>
            <input
              id="plan-query"
              name="query"
              type="text"
              required
              minLength={3}
              placeholder="a weekend of oysters and jazz in New Orleans…"
              className="input-field !py-3.5"
              defaultValue={initialQuery}
            />
          </div>

          <div>
            <label htmlFor="plan-days" className="voice-etch mb-2.5 block">
              Days
            </label>
            <select id="plan-days" name="days" defaultValue="2" className="input-field !w-24 !py-3.5">
              {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          <button type="submit" disabled={pending} className="btn-brass !py-3.5">
            {pending ? "Plotting…" : "Plot the route"}
          </button>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="voice-etch mr-1 !text-[0.5625rem]">Ideas</span>
          {JOURNEY_IDEAS.map((idea) => (
            <button
              key={idea}
              type="button"
              className="chip chip-link cursor-pointer"
              onClick={(event) => {
                const input = event.currentTarget
                  .closest("form")
                  ?.querySelector<HTMLInputElement>("#plan-query");
                if (input) {
                  input.value = idea;
                  input.focus();
                }
              }}
            >
              {idea}
            </button>
          ))}
        </div>

        {personalized && (
          <p className="mt-5 border-t border-(--line) pt-4 font-mono text-[0.6875rem] tracking-[0.08em] text-aurora-violet">
            ◈ personalization engaged — this route bends toward your linked taste
          </p>
        )}
      </form>

      {pending && (
        <div
          className="panel-etched flex flex-col items-center gap-4 px-6 py-16 text-center"
          role="status"
          aria-live="polite"
        >
          <span aria-hidden="true" className="star-twinkle text-2xl text-brass">
            ✦
          </span>
          <p className="voice-display text-lg text-starlight">Consulting the constellations…</p>
          <p className="font-mono text-xs text-faint">
            retrieval → ranking → planner, all within budget
          </p>
        </div>
      )}

      {!pending && state.status === "error" && (
        <div className="panel-etched border-aurora-rose/30 px-6 py-10 text-center" role="alert">
          <p className="voice-display text-lg text-aurora-rose">The route could not be plotted</p>
          <p className="mt-2 text-sm text-dim">{state.error}</p>
        </div>
      )}

      {!pending && state.status === "ok" && state.itinerary && (
        <ItineraryView itinerary={state.itinerary} />
      )}
    </div>
  );
}
