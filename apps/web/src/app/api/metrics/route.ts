import { metrics } from "@/lib/metrics";

/**
 * Prometheus scrape target. The nginx proxy refuses to forward this path,
 * so it is only reachable on the compose network (prometheus → web:3001).
 */
export const dynamic = "force-dynamic";

export async function GET() {
  const { registry } = metrics();
  const body = await registry.metrics();
  return new Response(body, {
    headers: { "content-type": registry.contentType },
  });
}
