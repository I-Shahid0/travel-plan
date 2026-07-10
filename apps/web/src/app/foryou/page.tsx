import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ListingCard } from "@/components/listing-card";
import { PageHeader } from "@/components/page-header";
import { Reveal } from "@/components/reveal";
import { recommendations } from "@/lib/api/query/client";
import { recentSearches, seedListings } from "@/lib/events";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "For you",
};

export default async function ForYouPage() {
  const session = await getSession();
  if (!session) {
    redirect("/sign-in?next=/foryou");
  }

  const userId = session.user.id;
  const [seeds, searches] = await Promise.all([
    seedListings(userId, 16),
    recentSearches(userId, 4),
  ]);

  const feed = await recommendations({
    seedListingIds: seeds.map((seed) => seed.listingId),
    limit: 18,
  });

  const seedTitles = new Map(seeds.map((seed) => [seed.listingId, seed.title]));
  const personalized = feed.strategy === "embedding_centroid";

  return (
    <div className="mx-auto max-w-7xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="Your private sky"
        title={
          personalized ? (
            <>
              Stars drawn to <em className="voice-wonk text-gradient-aurora">your orbit</em>
            </>
          ) : (
            <>
              A sky <em className="voice-wonk text-gradient-aurora">awaiting you</em>
            </>
          )
        }
      >
        <p className="mt-3 font-mono text-xs tracking-[0.08em] text-faint">
          {personalized ? (
            <>
              woven from <span className="text-aurora-violet">{feed.seed_count}</span> of your
              recent signals · recomputed on every visit
            </>
          ) : (
            <>the brightest stars for now — every place you visit teaches this page your taste</>
          )}
        </p>
      </PageHeader>

      {(seeds.length > 0 || searches.length > 0) && (
        <div className="panel-etched mb-10 flex flex-wrap items-center gap-2 px-5 py-4">
          <span className="voice-etch mr-1.5 !text-[0.5625rem]">Signals</span>
          {seeds.slice(0, 6).map((seed) => (
            <Link
              key={seed.listingId}
              href={`/listing/${encodeURIComponent(seed.listingId)}`}
              className="chip chip-link !py-0.5 !text-[0.625rem]"
            >
              ◉ {seed.title ?? "a charted place"}
            </Link>
          ))}
          {searches.map((query) => (
            <Link
              key={query}
              href={`/search?q=${encodeURIComponent(query)}`}
              className="chip chip-link !py-0.5 !text-[0.625rem]"
            >
              ✦ “{query}”
            </Link>
          ))}
          <Link
            href="/history"
            className="ml-auto font-mono text-[0.625rem] tracking-[0.1em] text-aurora-teal underline-offset-4 hover:underline"
          >
            full history →
          </Link>
        </div>
      )}

      {!personalized && (
        <div className="panel-etched mb-10 flex flex-col items-start gap-3 px-6 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="voice-display text-lg text-starlight">This sky is still learning you</p>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-dim">
              Browse the atlas, open a few places, run a search or two — each action becomes a
              signal, and this feed reshapes itself around them.
            </p>
          </div>
          <div className="flex shrink-0 gap-3">
            <Link href="/browse" className="btn-brass">
              Browse the atlas
            </Link>
            <Link href="/search" className="btn-ghost">
              Search
            </Link>
          </div>
        </div>
      )}

      {feed.results.length > 0 ? (
        <Reveal as="ul" className="grid list-none grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {feed.results.map((listing) => {
            const anchorId = feed.anchors?.[listing.id];
            const anchorTitle = anchorId ? seedTitles.get(anchorId) : null;
            return (
              <li key={listing.id}>
                <ListingCard
                  listing={listing}
                  hrefQuery={`src=foryou${anchorId ? `&anchor=${encodeURIComponent(anchorId)}` : ""}`}
                  note={
                    personalized
                      ? anchorTitle
                        ? `echoes ${anchorTitle}`
                        : "drawn from your recent orbit"
                      : undefined
                  }
                />
              </li>
            );
          })}
        </Reveal>
      ) : (
        <div className="panel-etched flex flex-col items-center gap-4 px-6 py-24 text-center">
          <span aria-hidden="true" className="text-3xl text-brass/60">
            ✧
          </span>
          <p className="voice-display text-xl text-starlight">The feed is dark</p>
          <p className="max-w-sm text-sm leading-relaxed text-dim">
            The recommendation engine returned nothing — it may be waking up. Try again shortly.
          </p>
        </div>
      )}
    </div>
  );
}
