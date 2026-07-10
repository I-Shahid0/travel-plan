import type { BrowseSort } from "@/lib/api/query/client";

/** URL-state for /browse — every filter lives in the query string. */
export interface BrowseState {
  city?: string;
  category?: string;
  priceMax?: number;
  minStars?: number;
  openOnly: boolean;
  sort: BrowseSort;
  page: number;
}

export function browseHref(state: BrowseState, overrides: Partial<BrowseState> = {}): string {
  const merged = { ...state, ...overrides };
  const params = new URLSearchParams();
  if (merged.city) params.set("city", merged.city);
  if (merged.category) params.set("category", merged.category);
  if (merged.priceMax) params.set("price_max", String(merged.priceMax));
  if (merged.minStars) params.set("min_stars", String(merged.minStars));
  if (merged.openOnly) params.set("open", "on");
  if (merged.sort !== "rating") params.set("sort", merged.sort);
  if (merged.page > 1) params.set("page", String(merged.page));
  const qs = params.toString();
  return qs ? `/browse?${qs}` : "/browse";
}
