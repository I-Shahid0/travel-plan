import Link from "next/link";

import { PaletteTrigger } from "@/components/command-palette";
import { CompassRose } from "@/components/compass";
import { SignOutButton } from "@/components/sign-out-button";
import { getSession } from "@/lib/session";

export async function Nav() {
  const session = await getSession();

  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:gap-6 sm:px-5">
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-2.5 text-brass transition-colors hover:text-brass-bright"
        >
          <CompassRose className="h-7 w-7" spin />
          <span className="voice-etch hidden !text-[0.8125rem] !tracking-[0.32em] text-starlight transition-colors group-hover:text-brass-bright sm:inline">
            Meridian
          </span>
        </Link>

        <nav className="flex min-w-0 items-center gap-0.5 sm:gap-1.5" aria-label="Primary">
          <PaletteTrigger />
          <Link
            href="/search"
            className="voice-etch rounded-full px-1.5 py-2 transition-colors hover:text-starlight sm:px-3"
          >
            Search
          </Link>
          <Link
            href="/browse"
            className="voice-etch rounded-full px-1.5 py-2 transition-colors hover:text-starlight sm:px-3"
          >
            Browse
          </Link>
          <Link
            href="/plan"
            className="voice-etch rounded-full px-1.5 py-2 transition-colors hover:text-starlight sm:px-3"
          >
            Plan
          </Link>
          {session ? (
            <div className="ml-1 flex min-w-0 items-center gap-0.5 border-l border-(--line) pl-1.5 sm:ml-2 sm:gap-1.5 sm:pl-3">
              <Link
                href="/foryou"
                className="voice-etch rounded-full px-1.5 py-2 whitespace-nowrap !text-aurora-violet transition-colors hover:!text-starlight sm:px-3"
              >
                For&nbsp;you
              </Link>
              <Link
                href="/history"
                className="voice-etch hidden rounded-full px-1.5 py-2 transition-colors hover:text-starlight sm:inline sm:px-3"
              >
                History
              </Link>
              {/* hidden on mobile (footer carries the link) so the row never
                  crushes the name to a single letter at 390px */}
              <Link
                href="/profile"
                className="voice-etch hidden truncate rounded-full px-1.5 py-2 !text-aurora-teal transition-colors hover:!text-starlight sm:inline sm:px-3"
                title={session.user.email}
              >
                {session.user.name?.split(" ")[0] ?? "Profile"}
              </Link>
              <SignOutButton />
            </div>
          ) : (
            <Link
              href="/sign-in"
              className="voice-etch ml-1 shrink-0 rounded-full border border-(--line) px-3 py-2 !text-starlight transition-all hover:border-brass hover:!text-brass-bright sm:ml-2 sm:px-4"
            >
              Sign in
            </Link>
          )}
        </nav>
      </div>
      {/* veil under the nav so content scrolls behind it gracefully */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-ink-950/90 via-ink-950/60 to-transparent backdrop-blur-md [mask-image:linear-gradient(to_bottom,black_60%,transparent)]"
      />
    </header>
  );
}
