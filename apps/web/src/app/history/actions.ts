"use server";

import { headers } from "next/headers";
import { revalidatePath } from "next/cache";

import { auth } from "@/lib/auth";
import { clearEvents } from "@/lib/events";

export interface ClearHistoryState {
  status: "idle" | "cleared" | "error";
  removed: number;
}

export async function clearHistory(): Promise<ClearHistoryState> {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    return { status: "error", removed: 0 };
  }
  const removed = await clearEvents(session.user.id);
  revalidatePath("/history");
  revalidatePath("/foryou");
  return { status: "cleared", removed };
}
