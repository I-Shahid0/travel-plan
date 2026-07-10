import { describe, expect, test } from "bun:test";

import { apiMetricsMiddleware, metrics, normalizeOperation } from "@/lib/metrics";

describe("normalizeOperation", () => {
  test("collapses listing ids to a bounded label", () => {
    expect(normalizeOperation("/listings/xK9-abc_123/similar")).toBe("/listings/{id}/similar");
    expect(normalizeOperation("/listings/xK9-abc_123")).toBe("/listings/{id}");
    expect(normalizeOperation("/listings")).toBe("/listings");
    expect(normalizeOperation("/search")).toBe("/search");
  });
});

describe("apiMetricsMiddleware", () => {
  test("observes request duration with service/operation/status labels", async () => {
    const middleware = apiMetricsMiddleware("query");
    const request = new Request("http://query:8000/listings/abc123/similar?limit=4");

    await middleware.onRequest?.({ request } as never);
    await middleware.onResponse?.({
      request,
      response: new Response("{}", { status: 200 }),
    } as never);

    const output = await metrics().registry.metrics();
    expect(output).toContain('operation="/listings/{id}/similar"');
    expect(output).toContain('service="query"');
  });

  test("counters register once despite repeated metrics() calls", () => {
    expect(metrics().registry).toBe(metrics().registry);
    metrics().eventsRecorded.inc({ type: "search" });
    metrics().recommendationsServed.inc({ strategy: "embedding_centroid" });
  });
});
