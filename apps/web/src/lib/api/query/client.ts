import "server-only";

import createClient from "openapi-fetch";

import { env } from "@/lib/env";
import { toApiError } from "@/lib/api/errors";
import { apiMetricsMiddleware, metrics } from "@/lib/metrics";

import type { components, paths } from "./schema";

export type SearchResponse = components["schemas"]["SearchResponse"];
export type ListingResult = components["schemas"]["ListingResult"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type BrowseResponse = components["schemas"]["BrowseResponse"];
export type BrowseFacets = components["schemas"]["BrowseFacets"];
export type ListingDetail = components["schemas"]["ListingDetail"];
export type SimilarResponse = components["schemas"]["SimilarResponse"];
export type RecommendationResponse = components["schemas"]["RecommendationResponse"];
export type EvalSplitResponse = components["schemas"]["EvalSplitResponse"];

export type BrowseSort = "rating" | "reviews" | "name";

export interface BrowseParams {
  limit?: number;
  offset?: number;
  sort?: BrowseSort;
  includeFacets?: boolean;
  city?: string;
  category?: string;
  priceMax?: number;
  minStars?: number;
  openOnly?: boolean;
}

export type SearchMode = "hybrid" | "dense" | "sparse" | "keyword";

export interface SearchParams {
  q: string;
  mode?: SearchMode;
  limit?: number;
  city?: string;
  priceMax?: number;
  category?: string;
  userId?: string;
  personalize?: boolean;
}

const client = createClient<paths>({
  baseUrl: env.QUERY_API_URL,
  // resolve fetch at call time so tests can substitute globalThis.fetch
  fetch: (request) => globalThis.fetch(request),
});
client.use(apiMetricsMiddleware("query"));

/** Typed GET /search against the query service. Server-side only. */
export async function search(params: SearchParams): Promise<SearchResponse> {
  const { data, error, response } = await client.GET("/search", {
    params: {
      query: {
        q: params.q,
        mode: params.mode ?? "hybrid",
        limit: params.limit ?? 24,
        city: params.city || null,
        price_max: params.priceMax ?? null,
        category: params.category || null,
        user_id: params.userId || null,
        personalize: params.personalize ?? Boolean(params.userId),
      },
    },
    cache: "no-store",
  });
  if (data) return data;
  throw toApiError("query", response.status, error);
}

/** Typed GET /listings — the Atlas browse surface. Results are user-independent, so short-lived caching is safe. */
export async function browse(params: BrowseParams = {}): Promise<BrowseResponse> {
  const { data, error, response } = await client.GET("/listings", {
    params: {
      query: {
        limit: params.limit ?? 24,
        offset: params.offset ?? 0,
        sort: params.sort ?? "rating",
        include_facets: params.includeFacets ?? false,
        city: params.city || null,
        category: params.category || null,
        price_max: params.priceMax ?? null,
        min_stars: params.minStars ?? null,
        open_only: params.openOnly ?? false,
      },
    },
    // No Next data cache: @vercel/otel's fetch wrapper corrupts cached bodies
    // under the bun runtime; freshness caching lives in Redis + nginx instead.
    cache: "no-store",
  });
  if (data) return data;
  throw toApiError("query", response.status, error);
}

/** Typed GET /listings/{id}. Returns null on 404 so pages can notFound(). */
export async function getListing(id: string): Promise<ListingDetail | null> {
  const { data, error, response } = await client.GET("/listings/{listing_id}", {
    params: { path: { listing_id: id } },
    cache: "no-store",
  });
  if (data) return data;
  if (response.status === 404) return null;
  throw toApiError("query", response.status, error);
}

/** Typed GET /listings/{id}/similar — embedding nearest-neighbours. */
export async function similarListings(id: string, limit = 8): Promise<SimilarResponse> {
  const { data, error, response } = await client.GET("/listings/{listing_id}/similar", {
    params: { path: { listing_id: id }, query: { limit } },
    cache: "no-store",
  });
  if (data) return data;
  throw toApiError("query", response.status, error);
}

/**
 * Typed POST /recommendations — seeds ordered most-recent-first; the backend
 * builds a recency-weighted embedding centroid and attributes each result to
 * its nearest seed (anchors).
 */
export async function recommendations(opts: {
  seedListingIds: string[];
  excludeListingIds?: string[];
  limit?: number;
}): Promise<RecommendationResponse> {
  const { data, error, response } = await client.POST("/recommendations", {
    body: {
      seed_listing_ids: opts.seedListingIds,
      exclude_listing_ids: opts.excludeListingIds ?? [],
      limit: opts.limit ?? 20,
    },
    cache: "no-store",
  });
  if (data) {
    metrics().recommendationsServed.inc({ strategy: data.strategy });
    return data;
  }
  throw toApiError("query", response.status, error);
}

/** GET /breakers — circuit-breaker states for the Observatory page. */
export async function queryBreakers(): Promise<Record<string, Record<string, unknown>> | null> {
  try {
    const { data } = await client.GET("/breakers", {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return (data as Record<string, Record<string, unknown>>) ?? null;
  } catch {
    return null;
  }
}

/** GET /eval/split — corpus train/test split metadata for the Observatory page. */
export async function evalSplit(): Promise<EvalSplitResponse | null> {
  try {
    const { data } = await client.GET("/eval/split", {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return data ?? null;
  } catch {
    return null;
  }
}

/** GET /health — listing count for the live telemetry strip. */
export async function queryHealth(): Promise<HealthResponse | null> {
  try {
    const { data } = await client.GET("/health", {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    return data ?? null;
  } catch {
    return null;
  }
}
