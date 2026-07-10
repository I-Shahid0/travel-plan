import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ClearHistoryButton } from "@/app/history/clear-button";
import { PageHeader } from "@/components/page-header";
import { eventCounts, recentEvents, type UserEvent } from "@/lib/events";
import { formatCount } from "@/lib/format";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "Your history",
};

/** History must always show the latest signals, never a cached page. */
export const dynamic = "force-dynamic";

const EVENT_GLYPH: Record<UserEvent["eventType"], string> = {
  search: "✦",
  listing_view: "◉",
  itinerary: "☾",
  recommendation_click: "➶",
};

const EVENT_LABEL: Record<UserEvent["eventType"], string> = {
  search: "Charted a query",
  listing_view: "Observed",
  itinerary: "Plotted a journey",
  recommendation_click: "Followed the feed to",
};

function eventHref(event: UserEvent): string | null {
  if (event.listingId) return `/listing/${encodeURIComponent(event.listingId)}`;
  if (event.eventType === "search" && event.query)
    return `/search?q=${encodeURIComponent(event.query)}`;
  if (event.eventType === "itinerary" && event.query)
    return `/plan?q=${encodeURIComponent(event.query)}`;
  return null;
}

function eventText(event: UserEvent): string {
  const title = typeof event.metadata.title === "string" ? event.metadata.title : null;
  if (event.listingId) return title ?? "a charted place";
  if (event.query) return `“${event.query}”`;
  return "—";
}

const dayFormat = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
});
const timeFormat = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
});

export default async function HistoryPage() {
  const session = await getSession();
  if (!session) {
    redirect("/sign-in?next=/history");
  }

  const userId = session.user.id;
  const [events, counts] = await Promise.all([recentEvents(userId, 120), eventCounts(userId)]);

  const byDay = new Map<string, UserEvent[]>();
  for (const event of events) {
    const key = dayFormat.format(event.createdAt);
    const bucket = byDay.get(key);
    if (bucket) bucket.push(event);
    else byDay.set(key, [event]);
  }

  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);

  return (
    <div className="mx-auto max-w-4xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="The observation log"
        title={
          <>
            Every star you&apos;ve <em className="voice-wonk text-gradient-aurora">touched</em>
          </>
        }
      >
        <p className="mt-3 font-mono text-xs tracking-[0.08em] text-faint">
          {formatCount(total)} signals recorded · these power{" "}
          <Link href="/foryou" className="text-aurora-violet underline-offset-4 hover:underline">
            your For-You sky
          </Link>
        </p>
      </PageHeader>

      {total > 0 && (
        <div className="mb-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(
            [
              ["search", "queries"],
              ["listing_view", "observations"],
              ["itinerary", "journeys"],
              ["recommendation_click", "feed follows"],
            ] as const
          ).map(([type, label]) => (
            <div key={type} className="panel-etched px-4 py-4 text-center">
              <p className="voice-display text-2xl text-starlight">
                {formatCount(counts[type] ?? 0)}
              </p>
              <p className="voice-etch mt-1 !text-[0.5625rem]">
                {EVENT_GLYPH[type]} {label}
              </p>
            </div>
          ))}
        </div>
      )}

      {events.length === 0 ? (
        <div className="panel-etched flex flex-col items-center gap-4 px-6 py-24 text-center">
          <span aria-hidden="true" className="text-3xl text-brass/60">
            ✧
          </span>
          <p className="voice-display text-xl text-starlight">The log is blank</p>
          <p className="max-w-sm text-sm leading-relaxed text-dim">
            Searches, places you open, and journeys you plot will be recorded here — and will
            teach your For-You sky what to surface.
          </p>
          <Link href="/browse" className="btn-brass mt-2">
            Start exploring
          </Link>
        </div>
      ) : (
        <>
          <ol className="list-none space-y-10">
            {Array.from(byDay.entries()).map(([day, dayEvents]) => (
              <li key={day}>
                <h2 className="voice-etch mb-4">{day}</h2>
                <ol className="list-none space-y-1 border-l border-(--line) pl-5">
                  {dayEvents.map((event) => {
                    const href = eventHref(event);
                    const body = (
                      <>
                        <span
                          aria-hidden="true"
                          className="w-5 shrink-0 text-center text-aurora-teal/80"
                        >
                          {EVENT_GLYPH[event.eventType]}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-sm text-dim">
                          <span className="text-faint">{EVENT_LABEL[event.eventType]} </span>
                          <span className="text-starlight">{eventText(event)}</span>
                        </span>
                        <time
                          dateTime={event.createdAt.toISOString()}
                          className="shrink-0 font-mono text-[0.625rem] tracking-[0.1em] text-faint"
                        >
                          {timeFormat.format(event.createdAt)}
                        </time>
                      </>
                    );
                    return (
                      <li key={event.id}>
                        {href ? (
                          <Link
                            href={href}
                            className="group -ml-[1.3125rem] flex items-center gap-3 rounded-lg border-l border-transparent py-2 pl-5 pr-3 transition-colors hover:border-brass hover:bg-white/[0.02]"
                          >
                            {body}
                          </Link>
                        ) : (
                          <span className="-ml-[1.3125rem] flex items-center gap-3 py-2 pl-5 pr-3">
                            {body}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ol>
              </li>
            ))}
          </ol>

          <div className="mt-12 flex items-center justify-between gap-4 border-t border-(--line) pt-6">
            <p className="max-w-sm text-xs leading-relaxed text-faint">
              Erasing the log resets your For-You sky to the brightest stars. This cannot be
              undone.
            </p>
            <ClearHistoryButton />
          </div>
        </>
      )}
    </div>
  );
}
