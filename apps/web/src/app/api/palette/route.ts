import { NextResponse } from "next/server";

import { search } from "@/lib/api/query/client";

export const dynamic = "force-dynamic";

/** Compact hit shape for the command palette — keep the payload tiny. */
export interface PaletteHit {
  id: string;
  title: string;
  city: string | null;
  state: string | null;
  stars: number | null;
  review_count: number;
  price_level: number | null;
  category: string | null;
}

/**
 * GET /api/palette?q=… — live hybrid-search hits for the ⌘K palette.
 * Never throws: the palette degrades to navigation-only on any failure.
 */
export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q")?.trim() ?? "";
  if (q.length < 2) {
    return NextResponse.json({ results: [] });
  }

  try {
    const response = await search({ q, limit: 7 });
    const results: PaletteHit[] = response.results.map((listing) => ({
      id: listing.id,
      title: listing.title,
      city: listing.city,
      state: listing.state,
      stars: listing.stars,
      review_count: listing.review_count,
      price_level: listing.price_level,
      category: listing.categories[0] ?? null,
    }));
    return NextResponse.json({ results });
  } catch {
    return NextResponse.json({ results: [] });
  }
}
