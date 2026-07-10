import "server-only";

import { getPool } from "@/lib/db";
import { metrics } from "@/lib/metrics";

/**
 * The event store: every meaningful user action lands in web_user_events and
 * the For-You feed + History page are derived from it. Recording is
 * fire-and-forget — an insert failure must never break a page render.
 */

export type UserEventType =
  | "search"
  | "listing_view"
  | "itinerary"
  | "recommendation_click";

export interface UserEvent {
  id: string;
  eventType: UserEventType;
  listingId: string | null;
  query: string | null;
  metadata: Record<string, unknown>;
  createdAt: Date;
}

export interface SeedListing {
  listingId: string;
  title: string | null;
  lastSeen: Date;
}

/** Duplicate suppression per type — RSC re-renders and refreshes shouldn't stack. */
const DEDUPE_WINDOW_SEC: Record<UserEventType, number> = {
  search: 120,
  listing_view: 120,
  itinerary: 30,
  recommendation_click: 30,
};

export async function recordEvent(opts: {
  userId: string;
  type: UserEventType;
  listingId?: string;
  query?: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  const { userId, type } = opts;
  const listingId = opts.listingId ?? null;
  const query = opts.query ?? null;
  const metadata = JSON.stringify(opts.metadata ?? {});
  try {
    await getPool().query(
      `INSERT INTO web_user_events (user_id, event_type, listing_id, query, metadata)
       SELECT $1, $2, $3, $4, $5::jsonb
       WHERE NOT EXISTS (
         SELECT 1 FROM web_user_events
         WHERE user_id = $1
           AND event_type = $2
           AND listing_id IS NOT DISTINCT FROM $3
           AND query IS NOT DISTINCT FROM $4
           AND created_at > now() - make_interval(secs => $6)
       )`,
      [userId, type, listingId, query, metadata, DEDUPE_WINDOW_SEC[type]],
    );
    metrics().eventsRecorded.inc({ type });
  } catch (err) {
    console.error("[events] failed to record", type, err);
  }
}

export async function recentEvents(userId: string, limit = 60): Promise<UserEvent[]> {
  const { rows } = await getPool().query(
    `SELECT id, event_type, listing_id, query, metadata, created_at
     FROM web_user_events
     WHERE user_id = $1
     ORDER BY created_at DESC
     LIMIT $2`,
    [userId, limit],
  );
  return rows.map((row) => ({
    id: String(row.id),
    eventType: row.event_type as UserEventType,
    listingId: row.listing_id,
    query: row.query,
    metadata: row.metadata ?? {},
    createdAt: row.created_at,
  }));
}

/**
 * Distinct listings the user interacted with, most recent first — the seed
 * set for /recommendations (order encodes recency for centroid weighting).
 */
export async function seedListings(userId: string, max = 16): Promise<SeedListing[]> {
  const { rows } = await getPool().query(
    `SELECT listing_id,
            max(created_at) AS last_seen,
            (array_agg(metadata ->> 'title' ORDER BY created_at DESC))[1] AS title
     FROM web_user_events
     WHERE user_id = $1 AND listing_id IS NOT NULL
     GROUP BY listing_id
     ORDER BY last_seen DESC
     LIMIT $2`,
    [userId, max],
  );
  return rows.map((row) => ({
    listingId: row.listing_id,
    title: row.title,
    lastSeen: row.last_seen,
  }));
}

export async function recentSearches(userId: string, max = 6): Promise<string[]> {
  const { rows } = await getPool().query(
    `SELECT query, max(created_at) AS last_seen
     FROM web_user_events
     WHERE user_id = $1 AND event_type = 'search' AND query IS NOT NULL
     GROUP BY query
     ORDER BY last_seen DESC
     LIMIT $2`,
    [userId, max],
  );
  return rows.map((row) => row.query as string);
}

export async function eventCounts(userId: string): Promise<Record<string, number>> {
  const { rows } = await getPool().query(
    `SELECT event_type, count(*)::int AS n
     FROM web_user_events
     WHERE user_id = $1
     GROUP BY event_type`,
    [userId],
  );
  return Object.fromEntries(rows.map((row) => [row.event_type, row.n]));
}

export async function clearEvents(userId: string): Promise<number> {
  const result = await getPool().query(`DELETE FROM web_user_events WHERE user_id = $1`, [
    userId,
  ]);
  return result.rowCount ?? 0;
}
