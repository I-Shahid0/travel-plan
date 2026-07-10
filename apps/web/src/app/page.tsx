import Link from "next/link";

import { Aurora } from "@/components/aurora";
import { ConstellationArt } from "@/components/constellation-art";
import { CityMarquee } from "@/components/marquee";
import { Reveal } from "@/components/reveal";
import { SampleQueries, SearchBar } from "@/components/search-bar";
import { Starfield } from "@/components/starfield";
import { queryHealth } from "@/lib/api/query/client";
import { formatCount } from "@/lib/format";

export default async function LandingPage() {
  const health = await queryHealth();

  return (
    <div className="relative">
      {/* ——— hero ——— */}
      <section className="relative flex min-h-[92svh] flex-col items-center justify-center overflow-hidden px-5 pt-24 pb-16">
        <Aurora />
        <Starfield />

        <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-col items-center text-center">
          <p className="voice-etch anim-rise mb-7 flex items-center gap-3">
            <span aria-hidden="true">✦</span> the atlas is open{" "}
            <span aria-hidden="true">✦</span>
          </p>

          <h1
            className="voice-display anim-rise text-[clamp(2.75rem,8vw,5.5rem)] leading-[1.02] font-light tracking-tight text-starlight"
            style={{ animationDelay: "80ms" }}
          >
            Navigate by
            <br />
            <em className="voice-wonk text-gradient-aurora pr-2 font-normal">what you long for</em>
          </h1>

          <p
            className="anim-rise mt-7 max-w-xl text-base leading-relaxed text-dim sm:text-lg"
            style={{ animationDelay: "160ms" }}
          >
            Meridian charts {health?.listings_count ? formatCount(health.listings_count) : "150,000+"}{" "}
            real places as stars in one navigable sky — searched by meaning, ranked to your taste,
            and plotted into journeys.
          </p>

          <div className="anim-rise mt-10 w-full max-w-2xl" style={{ animationDelay: "240ms" }}>
            <SearchBar autoFocus />
          </div>

          <div className="anim-rise mt-6" style={{ animationDelay: "320ms" }}>
            <SampleQueries />
          </div>

          <Link
            href="/browse"
            className="anim-rise mt-8 font-mono text-[0.6875rem] tracking-[0.18em] text-faint uppercase transition-colors hover:text-brass-bright"
            style={{ animationDelay: "400ms" }}
          >
            or unroll the full atlas ↓
          </Link>
        </div>

        {/* soft horizon */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-linear-to-t from-ink-950 to-transparent"
        />
      </section>

      <CityMarquee />

      {/* ——— the instruments ——— */}
      <section className="relative mx-auto max-w-6xl px-5 py-28">
        <Reveal className="mb-16 text-center">
          <p className="voice-etch mb-4">The instruments</p>
          <h2 className="voice-display mx-auto max-w-2xl text-3xl font-light text-starlight sm:text-4xl">
            A working observatory,
            <em className="voice-wonk text-gradient-brass"> not a mock-up</em>
          </h2>
        </Reveal>

        <Reveal className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <article className="panel-etched hairline-aurora p-7">
            <p className="voice-etch mb-5 text-aurora-teal!">01 · Retrieval</p>
            <h3 className="voice-display text-xl text-starlight">Hybrid search</h3>
            <p className="mt-3 text-sm leading-relaxed text-dim">
              Dense embeddings and sparse keywords fused with reciprocal-rank fusion, then re-ranked
              by a cross-encoder. Ask in plain language; the sky rearranges itself.
            </p>
            <Link href="/search?q=hidden%20speakeasy%20with%20live%20music" className="chip chip-link mt-6">
              Try a query →
            </Link>
          </article>

          <article className="panel-etched hairline-aurora p-7">
            <p className="voice-etch mb-5 text-aurora-violet!">02 · Personalization</p>
            <h3 className="voice-display text-xl text-starlight">Your own sky</h3>
            <p className="mt-3 text-sm leading-relaxed text-dim">
              Link a traveler profile and the ranking blends your taste vector into every search —
              the same query returns a different constellation for every navigator.
            </p>
            <Link href="/profile" className="chip chip-link mt-6">
              Link a profile →
            </Link>
          </article>

          <article className="panel-etched hairline-aurora p-7">
            <p className="voice-etch mb-5 text-aurora-rose!">03 · Itineraries</p>
            <h3 className="voice-display text-xl text-starlight">Plotted journeys</h3>
            <p className="mt-3 text-sm leading-relaxed text-dim">
              An LLM planner arranges the top-ranked places into a day-by-day route — behind a
              circuit breaker with a latency and cost budget, verdict included.
            </p>
            <Link href="/plan" className="chip chip-link mt-6">
              Plan a trip →
            </Link>
          </article>

          <article className="panel-etched hairline-aurora p-7">
            <p className="voice-etch mb-5 text-brass!">04 · Memory</p>
            <h3 className="voice-display text-xl text-starlight">A feed that learns</h3>
            <p className="mt-3 text-sm leading-relaxed text-dim">
              Every search, visit, and journey becomes a signal. The For-You sky rebuilds itself
              around your recent orbit — and tells you which star pulled each suggestion in.
            </p>
            <Link href="/foryou" className="chip chip-link mt-6">
              See your sky →
            </Link>
          </article>
        </Reveal>
      </section>

      {/* ——— specimen constellation strip ——— */}
      <section className="relative overflow-hidden border-y border-(--line) py-20">
        <Aurora dim />
        <div className="relative mx-auto max-w-6xl px-5">
          <Reveal className="mb-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="voice-etch mb-3">Cartography</p>
              <h2 className="voice-display max-w-xl text-2xl font-light text-starlight sm:text-3xl">
                Every place casts its own constellation
              </h2>
            </div>
            <p className="max-w-sm text-sm leading-relaxed text-faint">
              Sigils are drawn deterministically from each listing&apos;s identity and tinted by its
              category — the same place always rises under the same stars.
            </p>
          </Reveal>

          <Reveal className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {SPECIMENS.map((specimen) => (
              <figure key={specimen.id} className="panel overflow-hidden">
                <ConstellationArt
                  id={specimen.id}
                  categories={specimen.categories}
                  className="aspect-16/10 w-full"
                />
                <figcaption className="flex items-center justify-between px-4 py-3">
                  <span className="font-mono text-[0.625rem] tracking-[0.14em] text-dim uppercase">
                    {specimen.label}
                  </span>
                  <span aria-hidden="true" className="text-brass/50 text-xs">
                    ✦
                  </span>
                </figcaption>
              </figure>
            ))}
          </Reveal>
        </div>
      </section>

      {/* ——— telemetry / credibility ——— */}
      <section className="mx-auto max-w-6xl px-5 py-28">
        <Reveal className="panel-etched relative overflow-hidden p-8 sm:p-12">
          <div className="grid gap-10 md:grid-cols-[1.2fr_1fr] md:items-center">
            <div>
              <p className="voice-etch mb-4">Under the hood</p>
              <h2 className="voice-display text-2xl font-light text-starlight sm:text-3xl">
                End-to-end typed,
                <em className="voice-wonk text-gradient-aurora"> end to end real</em>
              </h2>
              <p className="mt-4 max-w-lg text-sm leading-relaxed text-dim">
                Every payload on this site is checked at compile time against the FastAPI OpenAPI
                schema: Pydantic models → generated TypeScript → Server Components. If the backend
                contract drifts, the build fails before you ever see it.
              </p>
            </div>

            <dl className="grid grid-cols-2 gap-x-6 gap-y-7 font-mono">
              <div>
                <dt className="voice-etch">Listings charted</dt>
                <dd className="mt-1.5 text-2xl text-brass-bright">
                  {health?.listings_count ? formatCount(health.listings_count) : "—"}
                </dd>
              </div>
              <div>
                <dt className="voice-etch">Engine status</dt>
                <dd className="mt-1.5 flex items-center gap-2 text-2xl">
                  <span
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      health?.status === "ok" ? "pulse-glow bg-aurora-teal" : "bg-aurora-rose"
                    }`}
                    aria-hidden="true"
                  />
                  <span className={health?.status === "ok" ? "text-aurora-teal" : "text-aurora-rose"}>
                    {health?.status === "ok" ? "aligned" : "adrift"}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="voice-etch">Retrieval modes</dt>
                <dd className="mt-1.5 text-2xl text-starlight">4</dd>
              </div>
              <div>
                <dt className="voice-etch">Type safety</dt>
                <dd className="mt-1.5 text-2xl text-starlight">100%</dd>
              </div>
            </dl>
          </div>
        </Reveal>
      </section>
    </div>
  );
}

const SPECIMENS = [
  { id: "specimen-cafe-arcturus", label: "Cafés", categories: ["Coffee & Tea"] },
  { id: "specimen-vega-kitchen", label: "Restaurants", categories: ["Restaurants"] },
  { id: "specimen-lyra-tavern", label: "Nightlife", categories: ["Bars", "Nightlife"] },
  { id: "specimen-altair-trailhead", label: "Outdoors", categories: ["Parks", "Hiking"] },
];
