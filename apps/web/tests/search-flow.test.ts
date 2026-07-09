import { afterEach, describe, expect, test } from "bun:test";

import { ApiError } from "@/lib/api/errors";
import { search, type SearchResponse } from "@/lib/api/query/client";

/**
 * Integration test for the search flow with mocked fetch — the fixture is
 * typed as the generated `SearchResponse`, so schema drift fails compilation
 * before it can fail in a browser.
 */

const FIXTURE: SearchResponse = {
  query: "late night ramen",
  total: 1499,
  mode: "hybrid",
  technique: "none",
  results: [
    {
      id: "6_T2xzR74JqGCTPefAD8Tw",
      title: "Morimoto",
      description: "Japanese fine dining",
      categories: ["Japanese", "Sushi Bars"],
      city: "Philadelphia",
      state: "PA",
      price_level: 4,
      stars: 4.5,
      review_count: 1914,
      primary_image_url: null,
      latitude: 39.9494,
      longitude: -75.1502,
    },
  ],
  query_understanding: { semantic_query: "late night ramen" },
  personalization: { requested: true, applied: true, alpha: 0.3 },
};

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("search flow", () => {
  test("returns the typed payload and encodes params", async () => {
    let requested: URL | null = null;
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      requested = new URL(input instanceof Request ? input.url : String(input));
      return new Response(JSON.stringify(FIXTURE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const response = await search({
      q: "late night ramen",
      mode: "hybrid",
      city: "Philadelphia",
      priceMax: 2,
      userId: "fCvMnJU1Z-XhAjKg99wK3Q",
      personalize: true,
    });

    expect(response.results[0]?.title).toBe("Morimoto");
    expect(response.personalization?.applied).toBe(true);

    expect(requested).not.toBeNull();
    const params = requested!.searchParams;
    expect(requested!.pathname).toBe("/search");
    expect(params.get("q")).toBe("late night ramen");
    expect(params.get("mode")).toBe("hybrid");
    expect(params.get("city")).toBe("Philadelphia");
    expect(params.get("price_max")).toBe("2");
    expect(params.get("user_id")).toBe("fCvMnJU1Z-XhAjKg99wK3Q");
    expect(params.get("personalize")).toBe("true");
  });

  test("maps FastAPI validation errors to a readable ApiError", async () => {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          detail: [{ loc: ["query", "q"], msg: "String should have at least 1 character", type: "string_too_short" }],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      )) as unknown as typeof fetch;

    expect(search({ q: "" })).rejects.toThrow(ApiError);
    try {
      await search({ q: "" });
    } catch (error) {
      const apiError = error as ApiError;
      expect(apiError.status).toBe(422);
      expect(apiError.message).toContain("q: String should have at least 1 character");
    }
  });
});
