import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Repo-root .env is the single source for DATABASE_URL; apps/web/.env holds web-only secrets.
loadEnvConfig(path.join(process.cwd(), "../.."));
loadEnvConfig(process.cwd());

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    // Enriched listing images live on arbitrary external hosts (Phase 8 finds
    // them across the open web) — the app displays but never stores them.
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

export default nextConfig;
