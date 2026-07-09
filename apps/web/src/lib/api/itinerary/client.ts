import "server-only";

import createClient from "openapi-fetch";

import { env } from "@/lib/env";
import { toApiError } from "@/lib/api/errors";

import type { components, paths } from "./schema";

export type ItineraryRequest = components["schemas"]["ItineraryRequest"];
export type ItineraryResponse = components["schemas"]["ItineraryResponse"];
export type BudgetReport = components["schemas"]["BudgetReport"];
export type ListingRef = components["schemas"]["ListingRef"];

const client = createClient<paths>({
  baseUrl: env.ITINERARY_API_URL,
  // resolve fetch at call time so tests can substitute globalThis.fetch
  fetch: (request) => globalThis.fetch(request),
});

/** Typed POST /itinerary against the itinerary service. Server-side only. */
export async function generateItinerary(
  body: ItineraryRequest,
): Promise<ItineraryResponse> {
  const { data, error, response } = await client.POST("/itinerary", {
    body,
    cache: "no-store",
  });
  if (data) return data;
  throw toApiError("itinerary", response.status, error);
}
