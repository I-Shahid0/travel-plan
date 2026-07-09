import "server-only";

import createClient from "openapi-fetch";

import { env } from "@/lib/env";
import { toApiError } from "@/lib/api/errors";

import type { components, paths } from "./schema";

export type SearchResponse = components["schemas"]["SearchResponse"];
export type ListingResult = components["schemas"]["ListingResult"];
export type HealthResponse = components["schemas"]["HealthResponse"];

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
