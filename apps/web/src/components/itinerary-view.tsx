import Link from "next/link";

import type { ItineraryResponse } from "@/lib/api/itinerary/client";
import { parseItinerary } from "@/lib/itinerary-parse";

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];

const TIME_OF_DAY =
  /^(early |late |mid)?(morning|afternoon|evening|night|midday|noon|breakfast|brunch|lunch|dinner|sunset)s?$/i;

function roman(n: number): string {
  return ROMAN[n - 1] ?? String(n);
}

/** The plotted journey: days as waypoints along an animated star route. */
export function ItineraryView({ itinerary }: { itinerary: ItineraryResponse }) {
  const parsed = parseItinerary(itinerary.itinerary);
  const degraded = itinerary.llm_provider === "template";

  return (
    <section aria-label="Your itinerary" className="anim-rise space-y-8">
      {/* ——— header ——— */}
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="voice-etch mb-2">The route</p>
          <h2 className="voice-display text-2xl font-light text-starlight">
            <em className="voice-wonk text-gradient-brass">“{itinerary.query}”</em>
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {degraded ? (
            <span
              className="chip !border-aurora-rose/40 !text-aurora-rose"
              title="The LLM circuit is open — this route was drawn by the deterministic fallback planner."
            >
              ◍ degraded · template planner
            </span>
          ) : (
            <span className="chip !border-aurora-teal/40 !text-aurora-teal">
              ◉ {itinerary.llm_provider} · {itinerary.llm_model}
            </span>
          )}
          {itinerary.user_id && (
            <span className="chip !text-aurora-violet" title="Personalized for this traveler profile">
              ◈ {itinerary.user_id.slice(0, 10)}…
            </span>
          )}
        </div>
      </header>

      {degraded && (
        <p className="panel border-l-2 !border-l-aurora-rose/60 px-5 py-4 text-sm leading-relaxed text-dim">
          The LLM planner is resting behind an open circuit breaker, so Meridian drew this route
          deterministically from the top-ranked places. The journey stands; the prose returns when
          the circuit closes.
        </p>
      )}

      {/* ——— intro prose ——— */}
      {parsed.intro.length > 0 && (
        <div className="max-w-2xl space-y-3">
          {parsed.intro.map((paragraph, i) => (
            <p key={i} className="text-sm leading-relaxed text-dim">
              {paragraph}
            </p>
          ))}
        </div>
      )}

      {/* ——— the route ——— */}
      {parsed.raw ? (
        <pre className="panel-etched overflow-x-auto p-6 font-mono text-sm leading-relaxed whitespace-pre-wrap text-dim">
          {parsed.raw}
        </pre>
      ) : (
        <ol className="relative list-none space-y-10 pl-9 sm:pl-12">
          {/* the meridian line the journey travels along */}
          <div
            aria-hidden="true"
            className="absolute top-2 bottom-2 left-[13px] w-px sm:left-[19px]"
            style={{
              background:
                "linear-gradient(180deg, transparent, var(--color-brass) 6%, var(--color-aurora-violet) 60%, transparent)",
              opacity: 0.5,
            }}
          />
          {parsed.days.map((day) => (
            <li key={day.day} className="relative">
              {/* waypoint marker */}
              <span
                aria-hidden="true"
                className="absolute top-1 -left-9 flex h-7 w-7 items-center justify-center rounded-full border border-brass/60 bg-ink-950 font-mono text-[0.625rem] text-brass sm:-left-12 sm:h-9 sm:w-9 sm:text-xs"
                style={{ boxShadow: "0 0 18px -4px rgba(228,197,128,0.5)" }}
              >
                {roman(day.day)}
              </span>

              <h3 className="voice-etch mb-4 flex items-baseline gap-3 pt-1.5 sm:pt-2.5">
                <span className="!text-brass-bright">Day {roman(day.day)}</span>
                {day.heading && <span className="text-dim normal-case">{day.heading}</span>}
              </h3>

              {day.stops.length > 0 && (
                <ul className="list-none space-y-3">
                  {day.stops.map((stop, i) => {
                    // "Morning: StrEATS Tours" → the place is the headline,
                    // the time of day becomes the etched kicker
                    const timeOfDay =
                      stop.detail && TIME_OF_DAY.test(stop.title.trim()) ? stop.title : null;
                    const headline = timeOfDay ? (stop.detail ?? stop.title) : stop.title;
                    const detail = timeOfDay ? null : stop.detail;
                    return (
                      <li key={i} className="panel hairline-aurora flex items-start gap-4 px-5 py-4">
                        <span aria-hidden="true" className="mt-0.5 text-sm text-brass/70">
                          ✦
                        </span>
                        <div className="min-w-0">
                          {timeOfDay && <p className="voice-etch mb-1 !text-[0.5625rem]">{timeOfDay}</p>}
                          <p className="voice-display text-[1.0625rem] text-starlight">{headline}</p>
                          {detail && (
                            <p className="mt-1 text-sm leading-relaxed text-dim">{detail}</p>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              {day.notes.length > 0 && (
                <div className="mt-3 space-y-2 pl-1">
                  {day.notes.map((note, i) => (
                    <p key={i} className="text-sm leading-relaxed text-faint">
                      {note}
                    </p>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}

      {/* ——— places used ——— */}
      {itinerary.listings_used.length > 0 && (
        <div>
          <p className="voice-etch mb-3">Charted from</p>
          <div className="flex flex-wrap gap-2">
            {itinerary.listings_used.map((listing) => (
              <Link
                key={listing.id}
                href={`/search?q=${encodeURIComponent(listing.title)}`}
                className="chip chip-link"
                title={listing.categories?.join(", ")}
              >
                {listing.title}
                {listing.city ? ` · ${listing.city}` : ""}
              </Link>
            ))}
          </div>
        </div>
      )}

      <BudgetInstrument itinerary={itinerary} />
    </section>
  );
}

/** Engine verdict: latency and cost against their budgets, brass-gauge style. */
function BudgetInstrument({ itinerary }: { itinerary: ItineraryResponse }) {
  const { budget } = itinerary;
  const latencyRatio = Math.min(budget.latency_ms / Math.max(budget.budget_ms, 1), 1);
  const costRatio = Math.min(budget.cost_usd_est / Math.max(budget.budget_usd, 1e-9), 1);

  return (
    <section className="panel-etched p-6" aria-label="Engine budget verdict">
      <header className="mb-6 flex items-center justify-between">
        <h3 className="voice-etch !text-brass">Engine verdict</h3>
        <span
          className={`font-mono text-[0.625rem] tracking-[0.2em] uppercase ${
            budget.within_budget ? "text-aurora-teal" : "text-aurora-rose"
          }`}
        >
          {budget.within_budget ? "● within budget" : "▲ over budget"}
        </span>
      </header>

      <div className="grid gap-x-10 gap-y-6 sm:grid-cols-2">
        <Gauge
          label="Latency"
          ratio={latencyRatio}
          reading={`${Math.round(budget.latency_ms)} ms`}
          ceiling={`budget ${Math.round(budget.budget_ms)} ms`}
          over={budget.latency_ms > budget.budget_ms}
        />
        <Gauge
          label="Est. cost"
          ratio={costRatio}
          reading={`$${budget.cost_usd_est.toFixed(5)}`}
          ceiling={`budget $${budget.budget_usd.toFixed(3)}`}
          over={budget.cost_usd_est > budget.budget_usd}
        />
      </div>

      <p className="mt-6 border-t border-(--line) pt-4 font-mono text-[0.6875rem] text-faint">
        tokens {itinerary.budget.input_tokens} in / {itinerary.budget.output_tokens} out · planner{" "}
        {itinerary.llm_provider}:{itinerary.llm_model}
      </p>
    </section>
  );
}

function Gauge({
  label,
  ratio,
  reading,
  ceiling,
  over,
}: {
  label: string;
  ratio: number;
  reading: string;
  ceiling: string;
  over: boolean;
}) {
  const percent = Math.round(ratio * 100);
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="voice-etch !text-[0.5625rem]">{label}</span>
        <span className={`font-mono text-sm ${over ? "text-aurora-rose" : "text-starlight"}`}>
          {reading}
        </span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-ink-800"
        role="meter"
        aria-label={label}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full transition-[width] duration-1000 ease-out"
          style={{
            width: `${Math.max(percent, 2)}%`,
            background: over
              ? "linear-gradient(90deg, #ff9db0, #ff6b8a)"
              : "linear-gradient(90deg, var(--color-aurora-teal), var(--color-brass))",
          }}
        />
      </div>
      <p className="mt-1.5 font-mono text-[0.625rem] text-faint">{ceiling}</p>
    </div>
  );
}
