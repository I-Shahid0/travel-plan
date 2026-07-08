import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const searchLatency = new Trend("search_latency", true);

export const options = {
  scenarios: {
    sustained: {
      executor: "ramping-arrival-rate",
      startRate: 1,
      timeUnit: "1s",
      preAllocatedVUs: 10,
      maxVUs: 40,
      stages: [
        { duration: "30s", target: 5 },
        { duration: "2m", target: 10 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<5000"],
    search_latency: ["p(95)<5000"],
  },
};

const baseUrl = __ENV.BASE_URL || "http://localhost:8000";
const queries = ["coffee", "pizza", "sushi", "brunch", "cocktails", "bakery"];

export default function () {
  const q = queries[Math.floor(Math.random() * queries.length)];
  const res = http.get(`${baseUrl}/search?q=${q}&limit=10`);
  searchLatency.add(res.timings.duration);
  check(res, {
    "status is 200": (r) => r.status === 200,
    "has results key": (r) => r.json("results") !== undefined,
  });
  sleep(0.05);
}

export function handleSummary(data) {
  const p95 = data.metrics.http_req_duration.values["p(95)"];
  const rps = data.metrics.http_reqs.values.rate;
  const summary = {
    phase: 5,
    tool: "k6",
    base_url: baseUrl,
    duration_sec: data.state.testRunDurationMs / 1000,
    requests: data.metrics.http_reqs.values.count,
    rps: rps,
    p95_ms: p95,
    failed_rate: data.metrics.http_req_failed.values.rate,
    thresholds_passed: Object.values(data.root_group.checks || {}).every((c) => c.passes > 0),
    recorded_at: new Date().toISOString(),
  };
  return {
    stdout: JSON.stringify(summary, null, 2),
    "results/loadtest-phase5.json": JSON.stringify(summary, null, 2),
  };
}
