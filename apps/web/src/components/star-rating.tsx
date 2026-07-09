import { formatCount } from "@/lib/format";

/** Five-pointed rating in brass — half-stars via clipped overlay. */
export function StarRating({
  stars,
  reviewCount,
}: {
  stars: number | null;
  reviewCount?: number;
}) {
  if (stars == null) return null;
  const percent = Math.max(0, Math.min(100, (stars / 5) * 100));

  return (
    <span className="inline-flex items-baseline gap-2" title={`${stars} out of 5`}>
      <span className="relative inline-block text-[0.8rem] leading-none tracking-[0.14em] text-faint/60 select-none">
        <span aria-hidden="true">★★★★★</span>
        <span
          aria-hidden="true"
          className="absolute inset-0 overflow-hidden whitespace-nowrap text-brass"
          style={{ width: `${percent}%` }}
        >
          ★★★★★
        </span>
        <span className="sr-only">{stars} out of 5 stars</span>
      </span>
      {reviewCount !== undefined && (
        <span className="font-mono text-[0.6875rem] text-faint">{formatCount(reviewCount)}</span>
      )}
    </span>
  );
}
