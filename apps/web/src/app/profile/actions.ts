"use server";

import { revalidatePath } from "next/cache";
import { headers } from "next/headers";

import { auth } from "@/lib/auth";
import { getSession } from "@/lib/session";

export interface ProfileState {
  status: "idle" | "ok" | "error";
  message: string | null;
}

const YELP_ID_PATTERN = /^[A-Za-z0-9_-]{10,40}$/;

export async function linkYelpProfile(
  _previous: ProfileState,
  formData: FormData,
): Promise<ProfileState> {
  const session = await getSession();
  if (!session) {
    return { status: "error", message: "Your session drifted — sign in again." };
  }

  const raw = String(formData.get("yelpUserId") ?? "").trim();

  if (raw && !YELP_ID_PATTERN.test(raw)) {
    return {
      status: "error",
      message: "That doesn't look like a Yelp user id (10–40 url-safe characters).",
    };
  }

  await auth.api.updateUser({
    headers: await headers(),
    body: { yelpUserId: raw || null },
  });

  revalidatePath("/profile");
  revalidatePath("/search");
  revalidatePath("/plan");

  return {
    status: "ok",
    message: raw ? "Profile linked — your sky is now your own." : "Profile unlinked.",
  };
}
