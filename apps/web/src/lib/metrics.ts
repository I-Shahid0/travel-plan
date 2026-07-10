/**
 * Prometheus metrics for the web app, scraped at GET /api/metrics.
 * Registry is cached on globalThis: dev HMR re-imports this module, and
 * prom-client throws on duplicate metric names.
 */
import type { Middleware } from "openapi-fetch";
import {
  Counter,
  Histogram,
  Registry,
  collectDefaultMetrics,
} from "prom-client";

interface MetricsBundle {
  registry: Registry;
  apiClientDuration: Histogram<"service" | "operation" | "status">;
  eventsRecorded: Counter<"type">;
  recommendationsServed: Counter<"strategy">;
}

const globalForMetrics = globalThis as unknown as { __meridianMetrics?: MetricsBundle };

function build(): MetricsBundle {
  const registry = new Registry();
  registry.setDefaultLabels({ app: "meridian-web" });
  try {
    collectDefaultMetrics({ register: registry });
  } catch {
    // Some default collectors probe Node internals that other runtimes lack.
  }

  return {
    registry,
    apiClientDuration: new Histogram({
      name: "meridian_api_client_duration_seconds",
      help: "Latency of typed calls from the web app to backend services",
      labelNames: ["service", "operation", "status"],
      buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
      registers: [registry],
    }),
    eventsRecorded: new Counter({
      name: "meridian_events_recorded_total",
      help: "User events written to the event store, by type",
      labelNames: ["type"],
      registers: [registry],
    }),
    recommendationsServed: new Counter({
      name: "meridian_recommendations_served_total",
      help: "For-You feeds served, by backend strategy",
      labelNames: ["strategy"],
      registers: [registry],
    }),
  };
}

export function metrics(): MetricsBundle {
  if (!globalForMetrics.__meridianMetrics) {
    globalForMetrics.__meridianMetrics = build();
  }
  return globalForMetrics.__meridianMetrics;
}

/** "/listings/xK9.../similar" -> "/listings/{id}/similar" — bounded label cardinality. */
export function normalizeOperation(pathname: string): string {
  return pathname.replace(/^\/listings\/[^/]+/, "/listings/{id}");
}

/**
 * openapi-fetch middleware timing every request a typed client makes —
 * one histogram covers search, browse, recommendations, and health probes.
 */
export function apiMetricsMiddleware(service: string): Middleware {
  const starts = new WeakMap<Request, number>();
  return {
    onRequest({ request }) {
      starts.set(request, performance.now());
      return request;
    },
    onResponse({ request, response }) {
      const start = starts.get(request);
      if (start !== undefined) {
        metrics().apiClientDuration.observe(
          {
            service,
            operation: normalizeOperation(new URL(request.url).pathname),
            status: String(response.status),
          },
          (performance.now() - start) / 1000,
        );
      }
      return response;
    },
    onError({ request }) {
      const start = starts.get(request);
      if (start !== undefined) {
        metrics().apiClientDuration.observe(
          {
            service,
            operation: normalizeOperation(new URL(request.url).pathname),
            status: "error",
          },
          (performance.now() - start) / 1000,
        );
      }
    },
  };
}
