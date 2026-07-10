import { resolveSyncDatabaseUrl } from "@/lib/database-url";

/**
 * Validated server-side environment. Accessors throw at first use with a
 * clear message instead of letting `undefined` leak into fetch URLs.
 * None of these are NEXT_PUBLIC_ — they must never reach the client bundle.
 */

/**
 * The Docker build stage sets placeholder values so `next build` can collect
 * page data without real secrets; they must never survive into a request.
 */
const BUILD_PLACEHOLDER = "meridian-build-placeholder";

function serverEnv(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name} — see repo root .env.example`,
    );
  }
  if (value.includes(BUILD_PLACEHOLDER) && process.env.NEXT_PHASE !== "phase-production-build") {
    throw new Error(
      `${name} is still the build placeholder — set the real value in the runtime environment`,
    );
  }
  return value;
}

export const env = {
  get QUERY_API_URL(): string {
    return serverEnv("QUERY_API_URL", "http://localhost:8000");
  },
  get ITINERARY_API_URL(): string {
    return serverEnv("ITINERARY_API_URL", "http://localhost:8002");
  },
  get DATABASE_URL(): string {
    return serverEnv("DATABASE_URL", resolveSyncDatabaseUrl());
  },
  get BETTER_AUTH_SECRET(): string {
    return serverEnv("BETTER_AUTH_SECRET");
  },
  get BETTER_AUTH_URL(): string {
    return serverEnv("BETTER_AUTH_URL", "http://localhost:3001");
  },
};
