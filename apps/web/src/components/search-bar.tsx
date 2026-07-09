import Link from "next/link";

/**
 * The observatory eyepiece: a GET form into /search, so queries live in the
 * URL and the whole flow works without client JS.
 */
export function SearchBar({
  defaultValue = "",
  size = "hero",
  autoFocus = false,
}: {
  defaultValue?: string;
  size?: "hero" | "compact";
  autoFocus?: boolean;
}) {
  const hero = size === "hero";

  return (
    <form action="/search" role="search" className="w-full">
      <div
        className={`group/search relative flex items-center gap-3 rounded-full border border-(--line) bg-ink-900/80 backdrop-blur-md transition-all duration-300 focus-within:border-aurora-violet/60 focus-within:shadow-[0_0_0_3px_rgba(139,124,255,0.14),0_0_50px_-10px_rgba(139,124,255,0.4)] ${
          hero ? "py-2 pr-2 pl-6" : "py-1.5 pr-1.5 pl-5"
        }`}
      >
        <svg
          viewBox="0 0 20 20"
          className={`shrink-0 text-faint transition-colors group-focus-within/search:text-aurora-violet ${hero ? "h-5 w-5" : "h-4 w-4"}`}
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <circle cx="9" cy="9" r="6.5" />
          <line x1="13.8" y1="13.8" x2="18" y2="18" strokeLinecap="round" />
        </svg>
        <input
          type="text"
          name="q"
          required
          minLength={1}
          defaultValue={defaultValue}
          autoFocus={autoFocus}
          placeholder={hero ? "a quiet coffee shop with good light…" : "search the atlas…"}
          aria-label="Search travel and experience listings"
          className={`w-full bg-transparent font-sans text-starlight outline-none placeholder:text-faint ${
            hero ? "py-2 text-base sm:text-lg" : "py-1.5 text-sm"
          }`}
        />
        <button type="submit" className={`btn-brass shrink-0 ${hero ? "" : "!px-4 !py-2.5"}`}>
          {hero ? "Chart it" : "Go"}
        </button>
      </div>
    </form>
  );
}

const SAMPLE_QUERIES = [
  "late night ramen",
  "rooftop cocktails at sunset",
  "vegan brunch with patio",
  "live jazz and small plates",
  "quiet bookshop cafe",
  "weekend food tour",
];

export function SampleQueries() {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <span className="voice-etch mr-1">Try</span>
      {SAMPLE_QUERIES.map((query) => (
        <Link
          key={query}
          href={`/search?q=${encodeURIComponent(query)}`}
          className="chip chip-link"
        >
          {query}
        </Link>
      ))}
    </div>
  );
}
