"use server";

import { headers } from "next/headers";

import { auth } from "@/lib/auth";
import { recordEvent } from "@/lib/events";

/**
 * Called from a client effect on the listing page so views reflect real
 * visits (RSC prefetches never fire it). Anonymous visitors are a no-op.
 * Arriving from the For-You feed additionally records the feed click with
 * its anchor, closing the recommendation loop.
 */
export async function recordListingView(input: {
  listingId: string;
  title: string;
  city: string | null;
  categories: string[];
  source?: string;
  anchorId?: string;
}): Promise<void> {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return;

  const userId = session.user.id;
  const metadata = {
    title: input.title,
    city: input.city,
    categories: input.categories.slice(0, 4),
  };

  await recordEvent({
    userId,
    type: "listing_view",
    listingId: input.listingId,
    metadata,
  });

  if (input.source === "foryou") {
    await recordEvent({
      userId,
      type: "recommendation_click",
      listingId: input.listingId,
      metadata: { ...metadata, anchor: input.anchorId ?? null },
    });
  }
}
