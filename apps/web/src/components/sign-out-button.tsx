"use client";

import { useRouter } from "next/navigation";

import { authClient } from "@/lib/auth-client";

export function SignOutButton() {
  const router = useRouter();

  return (
    <button
      type="button"
      className="voice-etch shrink-0 cursor-pointer rounded-full px-2 py-2 transition-colors hover:text-aurora-rose sm:px-3"
      onClick={async () => {
        await authClient.signOut();
        router.push("/");
        router.refresh();
      }}
    >
      {/* the full label overflows a 390px nav row — shorten below sm */}
      <span className="sm:hidden">Exit</span>
      <span className="hidden sm:inline">Sign out</span>
    </button>
  );
}
