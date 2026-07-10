/**
 * Minimal forward-only SQL migration runner for the web app's own tables
 * (Better Auth tables are managed separately by `bun run auth:migrate`).
 *
 * Applies apps/web/migrations/*.sql in filename order, tracking applied files
 * in web_migrations. Usage: `bun run db:migrate` (reads DATABASE_URL).
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { Pool } from "pg";

import { resolveSyncDatabaseUrl } from "../src/lib/database-url";

const MIGRATIONS_DIR = join(import.meta.dir, "..", "migrations");

const connectionString = resolveSyncDatabaseUrl();
if (!connectionString) {
  console.error("DATABASE_URL is required in the repo root .env (see .env.example)");
  process.exit(1);
}

const pool = new Pool({ connectionString });

async function main() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS web_migrations (
      name TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
  `);

  const files = (await readdir(MIGRATIONS_DIR)).filter((f) => f.endsWith(".sql")).sort();
  const { rows } = await pool.query<{ name: string }>("SELECT name FROM web_migrations");
  const applied = new Set(rows.map((r) => r.name));

  for (const file of files) {
    if (applied.has(file)) {
      console.log(`skip    ${file}`);
      continue;
    }
    const sql = await readFile(join(MIGRATIONS_DIR, file), "utf8");
    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      await client.query(sql);
      await client.query("INSERT INTO web_migrations (name) VALUES ($1)", [file]);
      await client.query("COMMIT");
      console.log(`applied ${file}`);
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }
}

main()
  .then(() => pool.end())
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
