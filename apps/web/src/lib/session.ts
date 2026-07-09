import "server-only";

import { headers } from "next/headers";
import { cache } from "react";

import { auth } from "@/lib/auth";

/** Session for the current request, deduped across Server Components. */
export const getSession = cache(async () => {
  return auth.api.getSession({ headers: await headers() });
});
