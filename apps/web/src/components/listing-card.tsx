import { ConstellationArt } from "@/components/constellation-art";
import { ListingImage } from "@/components/listing-image";
import { StarRating } from "@/components/star-rating";
import type { ListingResult } from "@/lib/api/query/client";
import { formatCoordinates, placeLine, priceGlyphs } from "@/lib/format";

/**
 * One place in the atlas. Enriched listings show their photograph;
 * everything else receives its constellation sigil.
 */
export function ListingCard({ listing, rank }: { listing: ListingResult; rank?: number }) {
  const price = priceGlyphs(listing.price_level);
  const place = placeLine(listing.city, listing.state);
  const coords = formatCoordinates(listing.latitude, listing.longitude);

  return (
    <article className="card-listing hairline-aurora group h-full">
      <div className="relative aspect-[16/10] overflow-hidden">
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
            className="h-full w-full"
          />
        )}
        {rank !== undefined && (
          <span className="absolute top-2.5 left-2.5 rounded-full border border-(--line) bg-ink-950/70 px-2 py-0.5 font-mono text-[0.625rem] tracking-[0.14em] text-dim backdrop-blur-sm">
            Nº {String(rank).padStart(2, "0")}
          </span>
        )}
        {coords && (
          <span className="absolute right-2.5 bottom-2 font-mono text-[0.5625rem] tracking-[0.12em] text-starlight/45">
            {coords}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2.5 p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="voice-display text-[1.0625rem] leading-snug font-medium text-starlight">
            {listing.title}
          </h3>
          {price && (
            <span className="mt-0.5 shrink-0 font-mono text-[0.6875rem] tracking-[0.2em] text-aurora-teal">
              {price}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between gap-3">
          <StarRating stars={listing.stars} reviewCount={listing.review_count} />
          {place && (
            <span className="truncate font-mono text-[0.6875rem] tracking-[0.06em] text-dim">
              {place}
            </span>
          )}
        </div>

        {listing.categories.length > 0 && (
          <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
            {listing.categories.slice(0, 3).map((category) => (
              <span key={category} className="chip !py-0.5 !text-[0.625rem]">
                {category}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
