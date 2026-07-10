"use server";

import { generateItinerary, type ItineraryResponse } from "@/lib/api/itinerary/client";
import { ApiError } from "@/lib/api/errors";
import { recordEvent } from "@/lib/events";
import { getSession } from "@/lib/session";

export interface PlanState {
  status: "idle" | "ok" | "error";
  itinerary: ItineraryResponse | null;
  error: string | null;
}

export async function planTrip(_previous: PlanState, formData: FormData): Promise<PlanState> {
  const session = await getSession();
  if (!session) {
    return { status: "error", itinerary: null, error: "Your session drifted — sign in again." };
  }

  const query = String(formData.get("query") ?? "").trim();
  const daysRaw = Number(formData.get("days"));
  const days = Number.isFinite(daysRaw) ? Math.min(Math.max(Math.round(daysRaw), 1), 7) : 2;

  if (!query) {
    return { status: "error", itinerary: null, error: "Describe the journey first." };
  }

  try {
    const itinerary = await generateItinerary({
      query,
      days,
      user_id: session.user.yelpUserId ?? null,
      top_k: 12,
    });
    await recordEvent({
      userId: session.user.id,
      type: "itinerary",
      query,
      metadata: {
        days,
        listings: itinerary.listings_used.length,
        provider: itinerary.llm_provider,
        withinBudget: itinerary.budget.within_budget,
      },
    });
    return { status: "ok", itinerary, error: null };
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : "The planning service is unreachable — try again shortly.";
    return { status: "error", itinerary: null, error: message };
  }
}
