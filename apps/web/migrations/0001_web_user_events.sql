-- Every meaningful user action becomes an event; the For-You feed and History
-- page are both built from this table. Denormalized display fields (title,
-- city) live in metadata so history rows survive listing re-ingests.
CREATE TABLE IF NOT EXISTS web_user_events (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('search', 'listing_view', 'itinerary', 'recommendation_click')
    ),
    listing_id TEXT,
    query TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_web_user_events_user_time
    ON web_user_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_web_user_events_user_listing
    ON web_user_events (user_id, listing_id)
    WHERE listing_id IS NOT NULL;
