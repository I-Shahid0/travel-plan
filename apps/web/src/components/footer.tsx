import Link from "next/link";

import { CompassRose } from "@/components/compass";

export function Footer() {
  return (
    <footer className="relative z-10 mt-28 border-t border-(--line)">
      <div className="mx-auto max-w-6xl px-5 py-14">
        <div className="flex flex-col items-start justify-between gap-10 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3 text-brass">
            <CompassRose className="h-8 w-8" />
            <div>
              <p className="voice-etch tracking-[0.32em]! text-starlight">Meridian</p>
              <p className="mt-1 text-xs text-faint">A celestial atlas of earthly places.</p>
            </div>
          </div>

          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <Link href="/search" className="voice-etch transition-colors hover:text-starlight">
              Search
            </Link>
            <Link href="/browse" className="voice-etch transition-colors hover:text-starlight">
              Browse
            </Link>
            <Link href="/plan" className="voice-etch transition-colors hover:text-starlight">
              Plan
            </Link>
            <Link href="/foryou" className="voice-etch transition-colors hover:text-starlight">
              For you
            </Link>
            <Link href="/history" className="voice-etch transition-colors hover:text-starlight">
              History
            </Link>
            <Link href="/profile" className="voice-etch transition-colors hover:text-starlight">
              Profile
            </Link>
            <Link
              href="/observatory"
              className="voice-etch transition-colors hover:text-starlight"
            >
              Observatory
            </Link>
            <a
              href="http://localhost:8000/docs"
              className="voice-etch transition-colors hover:text-starlight"
            >
              Query API
            </a>
          </nav>
        </div>

        <div className="rule-star mt-12 text-xs">✦</div>

        <p className="mt-8 text-center text-xs leading-relaxed text-faint">
          Charted from the Yelp Open Dataset · hybrid retrieval, cross-encoder reranking,
          personalization &amp; LLM trip planning
        </p>
      </div>
    </footer>
  );
}
