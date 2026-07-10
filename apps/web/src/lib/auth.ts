import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";

import { getPool } from "@/lib/db";
import { env } from "@/lib/env";

/**
 * Better Auth owns identity in the shared `retrieval` Postgres, in its own
 * auth_* tables (no collision with listings/interactions).
 *
 * `yelpUserId` bridges an account to a Yelp interaction user for
 * personalization — the FastAPI services keep speaking Yelp ids only.
 */
export const auth = betterAuth({
  baseURL: env.BETTER_AUTH_URL,
  secret: env.BETTER_AUTH_SECRET,
  database: getPool(),
  // The app is reachable both directly (:3001) and through the nginx
  // reverse proxy (:80) until a domain lands.
  trustedOrigins: ["http://localhost", "http://localhost:3001", "http://127.0.0.1"],
  emailAndPassword: {
    enabled: true,
  },
  user: {
    modelName: "auth_user",
    additionalFields: {
      yelpUserId: {
        type: "string",
        required: false,
      },
    },
  },
  session: {
    modelName: "auth_session",
    // No cookie cache: linking/unlinking a Yelp profile must reflect
    // immediately in Server Components, not after a TTL.
  },
  account: {
    modelName: "auth_account",
  },
  verification: {
    modelName: "auth_verification",
  },
  plugins: [nextCookies()],
});

export type Session = typeof auth.$Infer.Session;
