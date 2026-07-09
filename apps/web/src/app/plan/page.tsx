import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PlanConsole } from "@/app/plan/plan-console";
import { PageHeader } from "@/components/page-header";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "Plan a journey",
};

export default async function PlanPage() {
  const session = await getSession();
  if (!session) {
    redirect("/sign-in?next=/plan");
  }

  const yelpUserId = session.user.yelpUserId ?? null;

  return (
    <div className="mx-auto max-w-5xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="Route plotting"
        title={
          <>
            Plot a <em className="voice-wonk text-gradient-aurora">journey</em>
          </>
        }
      >
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-dim">
          Describe the trip you imagine. Meridian surfaces the strongest places for it, then the
          planner arranges them into a day-by-day route — with a live latency &amp; cost verdict
          from the engine.
        </p>
        {!yelpUserId && (
          <p className="mt-3 text-xs text-faint">
            Tip:{" "}
            <Link href="/profile" className="text-aurora-teal underline-offset-4 hover:underline">
              link a traveler profile
            </Link>{" "}
            and routes will bend toward your taste.
          </p>
        )}
      </PageHeader>

      <PlanConsole personalized={Boolean(yelpUserId)} />
    </div>
  );
}
