import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ConstellationArt } from "@/components/constellation-art";
import { ListingCard } from "@/components/listing-card";
import { ListingImage } from "@/components/listing-image";
import { RecordView } from "@/components/record-view";
import { Reveal } from "@/components/reveal";
import { StarRating } from "@/components/star-rating";
import { getListing, similarListings } from "@/lib/api/query/client";
import { attributeBadges } from "@/lib/attributes";
import { formatCoordinates, formatCount, placeLine, priceGlyphs } from "@/lib/format";

interface ListingPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export async function generateMetadata({ params }: ListingPageProps): Promise<Metadata> {
  const { id } = await params;
  const listing = await getListing(decodeURIComponent(id));
  return { title: listing ? listing.title : "Unknown star" };
}

export default async function ListingPage({ params, searchParams }: ListingPageProps) {
  const [{ id: rawId }, query] = await Promise.all([params, searchParams]);
  const id = decodeURIComponent(rawId);

  const listing = await getListing(id);
  if (!listing) notFound();

  const similar = await similarListings(id, 6).catch(() => null);

  const price = priceGlyphs(listing.price_level);
  const place = placeLine(listing.city, listing.state);
  const coords = formatCoordinates(listing.latitude, listing.longitude);
  const badges = attributeBadges(listing.attributes ?? {});
  const source = first(query.src);
  const anchorId = first(query.anchor);

  return (
    <div className="mx-auto max-w-6xl px-5 pt-28 pb-16">
      <RecordView
        listingId={listing.id}
        title={listing.title}
        city={listing.city}
        categories={listing.categories}
        source={source}
        anchorId={anchorId}
      />

      <nav aria-label="Breadcrumb" className="mb-6 font-mono text-[0.6875rem] tracking-[0.1em] text-faint">
        <Link href="/browse" className="transition-colors hover:text-starlight">
          Atlas
        </Link>
        <span aria-hidden="true"> · </span>
        {listing.city ? (
          <Link
            href={`/browse?city=${encodeURIComponent(listing.city)}`}
            className="transition-colors hover:text-starlight"
          >
            {listing.city}
          </Link>
        ) : (
          <span>uncharted</span>
        )}
        <span aria-hidden="true"> · </span>
        <span className="text-dim">{listing.title}</span>
      </nav>

      <div className="grid gap-8 lg:grid-cols-[1.1fr_1fr] lg:items-stretch">
        <div className="panel-etched hairline-aurora relative min-h-[280px] overflow-hidden sm:min-h-[360px]">
          {listing.primary_image_url ? (
            <ListingImage
              src={listing.primary_image_url}
              alt={listing.title}
              listingId={listing.id}
              categories={listing.categories}
            />
          ) : (
            <ConstellationArt
              id={listing.id}
              categories={listing.categories}
              className="absolute inset-0 h-full w-full"
            />
          )}
          {coords && (
            <span className="absolute right-4 bottom-3 font-mono text-[0.625rem] tracking-[0.14em] text-starlight/50">
              {coords}
            </span>
          )}
          <span className="absolute top-4 left-4 rounded-full border border-(--line) bg-ink-950/70 px-2.5 py-1 font-mono text-[0.625rem] tracking-[0.14em] text-dim backdrop-blur-sm">
            {listing.is_open ? "◉ charted & open" : "◌ archived star"}
          </span>
        </div>

        <div className="flex flex-col justify-center gap-5">
          <div>
            <p className="voice-etch mb-3">Fixed star</p>
            <h1 className="voice-display text-3xl font-light text-starlight sm:text-4xl">
              {listing.title}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <StarRating stars={listing.stars} reviewCount={listing.review_count} />
            {price && (
              <span className="font-mono text-xs tracking-[0.2em] text-aurora-teal">{price}</span>
            )}
            {place && (
              <span className="font-mono text-xs tracking-[0.06em] text-dim">{place}</span>
            )}
          </div>

          {listing.description && (
            <p className="max-w-prose text-sm leading-relaxed text-dim">{listing.description}</p>
          )}

          {listing.categories.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {listing.categories.map((category) => (
                <Link
                  key={category}
                  href={`/browse?category=${encodeURIComponent(category)}`}
                  className="chip chip-link !py-0.5 !text-[0.625rem]"
                >
                  {category}
                </Link>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-3 pt-1">
            <Link
              href={`/plan?q=${encodeURIComponent(
                `${listing.title}${listing.city ? ` and nearby gems in ${listing.city}` : ""}`,
              )}`}
              className="btn-brass"
            >
              Plan a journey here
            </Link>
            <Link
              href={`/search?q=${encodeURIComponent(
                listing.categories.slice(0, 2).join(" ") || listing.title,
              )}${listing.city ? `&city=${encodeURIComponent(listing.city)}` : ""}`}
              className="btn-ghost"
            >
              Chart more like this
            </Link>
          </div>
        </div>
      </div>

      {badges.length > 0 && (
        <section className="mt-10" aria-label="Field notes">
          <h2 className="voice-etch mb-4">Field notes</h2>
          <div className="flex flex-wrap gap-2">
            {badges.map((badge) => (
              <span key={badge.label} className="chip !py-1">
                {badge.label}
                {badge.detail && <span className="ml-1.5 text-faint">{badge.detail}</span>}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="mt-14" aria-label="Similar listings">
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <h2 className="voice-display text-2xl font-light text-starlight">
            Neighboring <em className="voice-wonk text-gradient-aurora">stars</em>
          </h2>
          <span className="font-mono text-[0.6875rem] tracking-[0.08em] text-faint">
            nearest in embedding space
          </span>
        </div>
        {similar && similar.results.length > 0 ? (
          <Reveal
            as="ul"
            className="grid list-none grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3"
          >
            {similar.results.map((item) => (
              <li key={item.id}>
                <ListingCard listing={item} />
              </li>
            ))}
          </Reveal>
        ) : (
          <p className="panel-etched px-6 py-10 text-center text-sm text-dim">
            This star sits alone — no neighbors charted yet.
          </p>
        )}
      </section>

      <p className="mt-10 font-mono text-[0.625rem] tracking-[0.1em] text-faint">
        id {listing.id} · {formatCount(listing.review_count)} observations logged
      </p>
    </div>
  );
}
