// No "server-only" here: the Better Auth CLI and migration scripts import
// this module outside a Next.js request context. env.ts keeps the same rule.
import { Pool } from "pg";

import { env } from "@/lib/env";

/**
 * One shared pg Pool for Better Auth and the event store. Cached on
 * globalThis so dev-server HMR doesn't leak connections.
 */
const globalForDb = globalThis as unknown as { __meridianPool?: Pool };

export function getPool(): Pool {
  if (!globalForDb.__meridianPool) {
    globalForDb.__meridianPool = new Pool({
      connectionString: env.DATABASE_URL,
      max: 10,
    });
  }
  return globalForDb.__meridianPool;
}
