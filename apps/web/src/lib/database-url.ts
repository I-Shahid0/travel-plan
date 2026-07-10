/**
 * Resolve the sync Postgres URL for node-postgres from repo-root .env vars.
 * Accepts either DATABASE_URL or DATABASE_URL_SYNC in sync or async form.
 */
export function resolveSyncDatabaseUrl(): string | undefined {
  const sync = process.env.DATABASE_URL_SYNC;
  const primary = process.env.DATABASE_URL;

  if (sync && !sync.includes("+asyncpg")) return sync;
  if (primary && !primary.includes("+asyncpg")) return primary;

  const asyncUrl = primary?.includes("+asyncpg")
    ? primary
    : sync?.includes("+asyncpg")
      ? sync
      : undefined;
  if (asyncUrl) {
    return asyncUrl.replace("postgresql+asyncpg://", "postgresql://");
  }

  return undefined;
}
