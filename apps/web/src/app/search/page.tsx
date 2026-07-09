import type { Metadata } from "next";

import { FilterRail } from "@/components/filter-rail";
import { InsightPanels } from "@/components/insight-panels";
import { ListingCard } from "@/components/listing-card";
import { PageHeader } from "@/components/page-header";
import { Reveal } from "@/components/reveal";
import { search, type SearchMode } from "@/lib/api/query/client";
import { formatCount } from "@/lib/format";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "Search",
};

interface SearchPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** For the personalize hidden+checkbox pair the later value is the live one. */
function last(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[value.length - 1] : value;
}

const MODES: SearchMode[] = ["hybrid", "dense", "sparse", "keyword"];

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  const q = first(params.q)?.trim() ?? "";
  const modeParam = first(params.mode);
  const mode: SearchMode = MODES.includes(modeParam as SearchMode)
    ? (modeParam as SearchMode)
    : "hybrid";
  const city = first(params.city)?.trim() || undefined;
  const priceRaw = Number(first(params.price_max));
  const priceMax = priceRaw >= 1 && priceRaw <= 4 ? priceRaw : undefined;
  const personalizeParam = last(params.personalize);

  const session = await getSession();
  const yelpUserId = session?.user.yelpUserId ?? undefined;
  const personalize = personalizeParam !== "off" && Boolean(yelpUserId);

  const response = q
    ? await search({
        q,
        mode,
        city,
        priceMax,
        userId: personalize ? yelpUserId : undefined,
        personalize,
      })
    : null;

  return (
    <div className="mx-auto max-w-7xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="Observation deck"
        title={
          q ? (
            <>
              Charting <em className="voice-wonk text-gradient-aurora">“{q}”</em>
            </>
          ) : (
            <>
              Search the <em className="voice-wonk text-gradient-aurora">atlas</em>
            </>
          )
        }
      >
        {response && (
          <p className="mt-3 font-mono text-xs tracking-[0.08em] text-faint">
            {formatCount(response.results.length)} places surfaced
            {response.mode !== "keyword" ? "" : ` of ${formatCount(response.total)} matches`} ·
            mode&nbsp;
            <span className="text-aurora-teal">{response.mode}</span>
            {response.personalization?.applied === true && (
              <>
                {" "}
                · <span className="text-aurora-violet">personalized</span>
              </>
            )}
          </p>
        )}
      </PageHeader>

      <div className="grid gap-10 lg:grid-cols-[280px_1fr]">
        <FilterRail
          q={q}
          mode={mode}
          city={city ?? ""}
          priceMax={priceMax}
          personalize={personalize}
          canPersonalize={Boolean(yelpUserId)}
          signedIn={Boolean(session)}
        />

        <div className="min-w-0">
          {!q && (
            <div className="panel-etched flex flex-col items-center gap-4 px-6 py-24 text-center">
              <span aria-hidden="true" className="text-3xl text-brass/60">
                ✦
              </span>
              <p className="voice-display text-xl text-starlight">The sky is quiet</p>
              <p className="max-w-sm text-sm leading-relaxed text-dim">
                Describe what you long for — a mood, a meal, a neighborhood — and Meridian will
                chart the places that answer.
              </p>
            </div>
          )}

          {response && response.results.length === 0 && (
            <div className="panel-etched flex flex-col items-center gap-4 px-6 py-24 text-center">
              <span aria-hidden="true" className="text-3xl text-brass/60">
                ✧
              </span>
              <p className="voice-display text-xl text-starlight">Nothing rose above the horizon</p>
              <p className="max-w-sm text-sm leading-relaxed text-dim">
                No places matched this query with the current filters. Loosen the filters or try
                different words.
              </p>
            </div>
          )}

          {response && response.results.length > 0 && (
            <>
              <Reveal as="ul" className="grid list-none grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {response.results.map((listing, index) => (
                  <li key={listing.id}>
                    <ListingCard listing={listing} rank={index + 1} />
                  </li>
                ))}
              </Reveal>

              <InsightPanels
                queryUnderstanding={response.query_understanding ?? null}
                personalization={response.personalization ?? null}
                technique={response.technique ?? null}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
