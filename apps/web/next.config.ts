import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    // Enriched listing images live on arbitrary external hosts (Phase 8 finds
    // them across the open web) — the app displays but never stores them.
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

export default nextConfig;
