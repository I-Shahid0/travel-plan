import type { Metadata } from "next";
import Link from "next/link";

import { BrowseRail } from "@/app/browse/browse-rail";
import { ListingCard } from "@/components/listing-card";
import { PageHeader } from "@/components/page-header";
import { Reveal } from "@/components/reveal";
import { browse, type BrowseSort } from "@/lib/api/query/client";
import { browseHref, type BrowseState } from "@/lib/browse";
import { formatCount } from "@/lib/format";

export const metadata: Metadata = {
  title: "Browse the atlas",
};

const PAGE_SIZE = 24;
const SORTS: BrowseSort[] = ["rating", "reviews", "name"];

interface BrowsePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** Later value wins — used for the open-only hidden+checkbox pair. */
function last(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[value.length - 1] : value;
}

export default async function BrowsePage({ searchParams }: BrowsePageProps) {
  const params = await searchParams;

  const sortParam = first(params.sort);
  const priceRaw = Number(first(params.price_max));
  const starsRaw = Number(first(params.min_stars));
  const pageRaw = Number(first(params.page));

  const state: BrowseState = {
    city: first(params.city)?.trim() || undefined,
    category: first(params.category)?.trim() || undefined,
    priceMax: priceRaw >= 1 && priceRaw <= 4 ? priceRaw : undefined,
    minStars: starsRaw >= 1 && starsRaw <= 5 ? starsRaw : undefined,
    openOnly: last(params.open) === "on",
    sort: SORTS.includes(sortParam as BrowseSort) ? (sortParam as BrowseSort) : "rating",
    page: Number.isInteger(pageRaw) && pageRaw > 1 ? pageRaw : 1,
  };

  const response = await browse({
    limit: PAGE_SIZE,
    offset: (state.page - 1) * PAGE_SIZE,
    sort: state.sort,
    includeFacets: true,
    city: state.city,
    category: state.category,
    priceMax: state.priceMax,
    minStars: state.minStars,
    openOnly: state.openOnly,
  });

  const pageCount = Math.max(1, Math.ceil(Math.min(response.total, 10_000) / PAGE_SIZE));
  const facets = response.facets;
  const hasFilters = Boolean(
    state.city || state.category || state.priceMax || state.minStars || state.openOnly,
  );

  return (
    <div className="mx-auto max-w-7xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="The atlas, unabridged"
        title={
          <>
            Browse every <em className="voice-wonk text-gradient-aurora">charted star</em>
          </>
        }
      >
        <p className="mt-3 font-mono text-xs tracking-[0.08em] text-faint">
          {formatCount(response.total)} places under these skies
          {state.city && (
            <>
              {" "}
              · above <span className="text-aurora-teal">{state.city}</span>
            </>
          )}
          {state.category && (
            <>
              {" "}
              · charted as <span className="text-aurora-violet">{state.category}</span>
            </>
          )}
          {hasFilters && (
            <>
              {" "}
              ·{" "}
              <Link href="/browse" className="text-brass underline-offset-4 hover:underline">
                clear all
              </Link>
            </>
          )}
        </p>
      </PageHeader>

      <div className="grid gap-10 lg:grid-cols-[280px_1fr]">
        <BrowseRail state={state} />

        <div className="min-w-0">
          {facets && (facets.cities.length > 0 || facets.categories.length > 0) && (
            <div className="mb-8 space-y-4">
              {facets.cities.length > 0 && (
                <div className="flex flex-wrap items-baseline gap-1.5">
                  <span className="voice-etch mr-1.5 !text-[0.5625rem]">Skies</span>
                  {facets.cities.slice(0, 8).map((facet) => {
                    const active = state.city === facet.value;
                    return (
                      <Link
                        key={facet.value}
                        href={browseHref(state, { city: active ? undefined : facet.value, page: 1 })}
                        className={`chip chip-link !py-0.5 !text-[0.625rem] ${active ? "chip-active" : ""}`}
                      >
                        {facet.value}
                        <span className="ml-1 text-faint">{formatCount(facet.count)}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
              {facets.categories.length > 0 && (
                <div className="flex flex-wrap items-baseline gap-1.5">
                  <span className="voice-etch mr-1.5 !text-[0.5625rem]">Charted as</span>
                  {facets.categories.slice(0, 12).map((facet) => {
                    const active = state.category === facet.value;
                    return (
                      <Link
                        key={facet.value}
                        href={browseHref(state, {
                          category: active ? undefined : facet.value,
                          page: 1,
                        })}
                        className={`chip chip-link !py-0.5 !text-[0.625rem] ${active ? "chip-active" : ""}`}
                      >
                        {facet.value}
                        <span className="ml-1 text-faint">{formatCount(facet.count)}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {response.results.length === 0 ? (
            <div className="panel-etched flex flex-col items-center gap-4 px-6 py-24 text-center">
              <span aria-hidden="true" className="text-3xl text-brass/60">
                ✧
              </span>
              <p className="voice-display text-xl text-starlight">These skies are empty</p>
              <p className="max-w-sm text-sm leading-relaxed text-dim">
                No charted place matches every filter at once. Loosen one and the stars return.
              </p>
              <Link href="/browse" className="btn-ghost mt-2">
                Clear the filters
              </Link>
            </div>
          ) : (
            <>
              <Reveal
                as="ul"
                className="grid list-none grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3"
              >
                {response.results.map((listing, index) => (
                  <li key={listing.id}>
                    <ListingCard
                      listing={listing}
                      rank={(state.page - 1) * PAGE_SIZE + index + 1}
                    />
                  </li>
                ))}
              </Reveal>

              <nav
                aria-label="Pagination"
                className="mt-10 flex items-center justify-between gap-4 border-t border-(--line) pt-6"
              >
                {state.page > 1 ? (
                  <Link href={browseHref(state, { page: state.page - 1 })} className="btn-ghost">
                    ← Previous
                  </Link>
                ) : (
                  <span className="btn-ghost pointer-events-none opacity-30">← Previous</span>
                )}
                <span className="font-mono text-[0.6875rem] tracking-[0.14em] text-faint">
                  LEAF {String(state.page).padStart(2, "0")} / {formatCount(pageCount)}
                </span>
                {state.page < pageCount ? (
                  <Link href={browseHref(state, { page: state.page + 1 })} className="btn-ghost">
                    Next →
                  </Link>
                ) : (
                  <span className="btn-ghost pointer-events-none opacity-30">Next →</span>
                )}
              </nav>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
