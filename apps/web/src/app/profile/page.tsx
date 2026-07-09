import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ProfileConsole } from "@/app/profile/profile-console";
import { PageHeader } from "@/components/page-header";
import { getSession } from "@/lib/session";

export const metadata: Metadata = {
  title: "Navigator profile",
};

export default async function ProfilePage() {
  const session = await getSession();
  if (!session) {
    redirect("/sign-in?next=/profile");
  }

  return (
    <div className="mx-auto max-w-4xl px-5 pt-28 pb-16">
      <PageHeader
        kicker="Navigator"
        title={
          session.user.name ? (
            <em className="voice-wonk text-gradient-brass">{session.user.name}</em>
          ) : (
            "Your profile"
          )
        }
      >
        <p className="mt-2 font-mono text-xs text-faint">{session.user.email}</p>
      </PageHeader>

      <ProfileConsole currentYelpUserId={session.user.yelpUserId ?? null} />
    </div>
  );
}
