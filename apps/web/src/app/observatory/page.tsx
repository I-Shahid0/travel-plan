import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { itineraryHealth } from "@/lib/api/itinerary/client";
import { evalSplit, queryBreakers, queryHealth } from "@/lib/api/query/client";
import { formatCount } from "@/lib/format";

export const metadata: Metadata = {
  title: "Observatory",
};

/** Live instrument readings — never cache this page. */
export const dynamic = "force-dynamic";

function StatusLamp({ ok, label }: { ok: boolean | null; label: string }) {
  const tone =
    ok === null ? "text-aurora-rose" : ok ? "text-aurora-teal" : "text-brass";
  const word = ok === null ? "unreachable" : ok ? "nominal" : "degraded";
  return (
    <span className={`font-mono text-[0.6875rem] tracking-[0.14em] ${tone}`}>
      {ok === null ? "◌" : "◉"} {label} · {word}
    </span>
  );
}

export default async function ObservatoryPage() {
  const [query, itinerary, breakers, split] = await Promise.all([
    queryHealth(),
    itineraryHealth(),
    queryBreakers(),
    evalSplit(),
  ]);

  const breakerEntries = Object.entries(breakers ?? {});

  return (
    <div className="mx-auto max-w-5xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="Instrument room"
        title={
          <>
            The <em className="voice-wonk text-gradient-aurora">observatory</em>
          </>
        }
      >
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-dim">
          Live readings from every instrument behind Meridian — service health, circuit
          breakers, and the evaluation split the engine is measured against. The deeper gauges
          live in Grafana, Jaeger, and Prometheus.
        </p>
      </PageHeader>

      <section aria-label="Service health" className="grid gap-4 sm:grid-cols-2">
        <div className="panel-etched hairline-aurora p-6">
          <p className="voice-etch mb-3">Retrieval engine</p>
          <StatusLamp ok={query ? query.status === "ok" : null} label="query-service" />
          <p className="voice-display mt-4 text-3xl font-light text-starlight">
            {query?.listings_count != null ? formatCount(query.listings_count) : "—"}
          </p>
          <p className="mt-1 text-xs text-faint">charted places under management</p>
        </div>

        <div className="panel-etched hairline-aurora p-6">
          <p className="voice-etch mb-3">Route planner</p>
          <StatusLamp
            ok={itinerary ? String(itinerary.status ?? "") === "ok" : null}
            label="itinerary-service"
          />
          <p className="voice-display mt-4 text-3xl font-light text-starlight">
            {itinerary?.llm_provider ? String(itinerary.llm_provider) : "—"}
          </p>
          <p className="mt-1 text-xs text-faint">
            active planning model
            {itinerary?.llm_model ? ` · ${String(itinerary.llm_model)}` : ""}
          </p>
        </div>
      </section>

      <section aria-label="Circuit breakers" className="mt-8">
        <h2 className="voice-etch mb-4">Circuit breakers</h2>
        {breakerEntries.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {breakerEntries.map(([name, state]) => {
              const stateWord = String(state.state ?? "unknown");
              const closed = stateWord === "closed";
              return (
                <div key={name} className="panel-etched flex items-center justify-between p-5">
                  <div>
                    <p className="font-mono text-xs tracking-[0.1em] text-starlight">{name}</p>
                    <p className="mt-1 text-xs text-faint">
                      {String(state.failure_count ?? 0)} / {String(state.failure_threshold ?? "?")}{" "}
                      failures toward opening
                    </p>
                  </div>
                  <span
                    className={`font-mono text-[0.6875rem] tracking-[0.14em] ${
                      closed ? "text-aurora-teal" : "text-aurora-rose"
                    }`}
                  >
                    {closed ? "◉ closed" : `◌ ${stateWord}`}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="panel-etched px-6 py-8 text-center text-sm text-dim">
            Breaker states unavailable — the query service may be waking up.
          </p>
        )}
      </section>

      {split && (
        <section aria-label="Evaluation split" className="mt-8">
          <h2 className="voice-etch mb-4">Evaluation split</h2>
          <div className="panel-etched grid gap-6 p-6 sm:grid-cols-3">
            <div>
              <p className="voice-display text-2xl font-light text-starlight">
                {formatCount(split.train_count)}
              </p>
              <p className="mt-1 text-xs text-faint">training interactions</p>
            </div>
            <div>
              <p className="voice-display text-2xl font-light text-starlight">
                {formatCount(split.test_count)}
              </p>
              <p className="mt-1 text-xs text-faint">held-out test interactions</p>
            </div>
            <div>
              <p className="voice-display text-2xl font-light text-starlight">
                {split.cutoff_date}
              </p>
              <p className="mt-1 text-xs text-faint">temporal cutoff — no leakage</p>
            </div>
          </div>
        </section>
      )}

      <section aria-label="Deeper instruments" className="mt-8">
        <h2 className="voice-etch mb-4">Deeper instruments</h2>
        <div className="flex flex-wrap gap-2">
          <a href="http://localhost:3000" className="chip chip-link">
            Grafana dashboards
          </a>
          <a href="http://localhost:16686" className="chip chip-link">
            Jaeger traces
          </a>
          <a href="http://localhost:9090" className="chip chip-link">
            Prometheus
          </a>
          <a href="http://localhost:8000/docs" className="chip chip-link">
            Query API docs
          </a>
          <a href="http://localhost:8002/docs" className="chip chip-link">
            Itinerary API docs
          </a>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-faint">
          Every page render in this app emits OpenTelemetry spans that join the backend traces —
          find a slow search in Jaeger and walk it from the browser request down to the pgvector
          scan.
        </p>
      </section>
    </div>
  );
}
