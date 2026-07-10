/**
 * Next.js instrumentation hook — registers OpenTelemetry when OTEL_ENABLED,
 * mirroring the FastAPI services. Spans flow to the same collector (tail
 * sampling) and land in Jaeger as one distributed trace: browser request →
 * web render → query-service → reranker.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (process.env.OTEL_ENABLED !== "true") return;

  const { registerOTel } = await import("@vercel/otel");
  registerOTel({
    serviceName: process.env.OTEL_SERVICE_NAME ?? "meridian-web",
    instrumentationConfig: {
      fetch: {
        // Inject traceparent into outbound fetches to our own services only.
        propagateContextUrls: [/^https?:\/\/(localhost|127\.0\.0\.1|query|itinerary)(:\d+)?\//],
      },
    },
  });
}
