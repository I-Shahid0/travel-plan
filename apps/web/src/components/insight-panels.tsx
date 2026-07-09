import { Reveal } from "@/components/reveal";

/**
 * Instrument readouts: how the engine read the query, and how the ranking
 * was bent toward the signed-in traveler. These fields are loosely typed
 * dicts in the OpenAPI contract (documented v1 looseness) — everything is
 * defensively narrowed before display.
 */

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function Readout({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="voice-etch truncate !text-[0.5625rem]">{label}</dt>
      <dd
        className={`mt-1 truncate font-mono text-sm ${accent ? "text-aurora-teal" : "text-starlight"}`}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}

export function InsightPanels({
  queryUnderstanding,
  personalization,
  technique,
}: {
  queryUnderstanding: Record<string, unknown> | null;
  personalization: Record<string, unknown> | null;
  technique: string | null;
}) {
  const qu = asRecord(queryUnderstanding);
  const quFilters = asRecord(qu?.filters);
  const quUsage = asRecord(qu?.usage);
  const p = asRecord(personalization);

  if (!qu && !p) return null;

  return (
    <Reveal className="mt-12 grid gap-5 lg:grid-cols-2">
      {qu && (
        <section className="panel-etched p-6">
          <header className="mb-5 flex items-center justify-between">
            <h2 className="voice-etch !text-aurora-teal">Query lens</h2>
            <span className="font-mono text-[0.625rem] text-faint">
              technique · {show(technique ?? quUsage?.technique)}
            </span>
          </header>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <div className="col-span-2 sm:col-span-3">
              <dt className="voice-etch !text-[0.5625rem]">Semantic query</dt>
              <dd className="mt-1 font-mono text-sm break-words text-starlight">
                {show(qu.semantic_query)}
              </dd>
            </div>
            <Readout label="City filter" value={show(quFilters?.city)} />
            <Readout label="Price ≤" value={show(quFilters?.price_max)} />
            <Readout label="Category" value={show(quFilters?.category)} />
            <Readout label="LLM calls" value={show(quUsage?.llm_calls)} />
            <Readout label="Tokens in / out" value={`${show(quUsage?.input_tokens)} / ${show(quUsage?.output_tokens)}`} />
            <Readout label="QU latency" value={`${show(quUsage?.latency_ms)} ms`} />
          </dl>
        </section>
      )}

      {p && (
        <section className="panel-etched p-6">
          <header className="mb-5 flex items-center justify-between">
            <h2 className="voice-etch !text-aurora-violet">Personal sky</h2>
            <span
              className={`font-mono text-[0.625rem] ${p.applied === true ? "text-aurora-teal" : "text-faint"}`}
            >
              {p.applied === true ? "● applied" : "○ not applied"}
            </span>
          </header>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
            <Readout label="Navigator" value={show(p.user_id)} accent />
            <Readout label="Taste blend" value={show(p.alpha)} />
            <Readout label="Signal" value={show(p.signal)} />
            <Readout label="Cold start" value={show(p.cold_start)} />
            <Readout label="Cache hit" value={show(p.cache_hit)} />
            <Readout label="Candidates" value={show(p.candidate_count)} />
          </dl>
          <p className="mt-5 border-t border-(--line) pt-4 text-xs leading-relaxed text-faint">
            The engine blends this traveler&apos;s taste vector into the ranking with weight α —
            the same query charts a different sky for every navigator.
          </p>
        </section>
      )}
    </Reveal>
  );
}
