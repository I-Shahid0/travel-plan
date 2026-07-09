import { describe, expect, test } from "bun:test";

import { detailToMessage } from "@/lib/api/errors";

describe("detailToMessage", () => {
  test("passes HTTPException string detail through", () => {
    expect(detailToMessage("No listings found for query", 404)).toBe(
      "No listings found for query",
    );
  });

  test("joins validation errors with field paths", () => {
    const detail = [
      { loc: ["query", "days"], msg: "Input should be less than or equal to 14" },
      { loc: ["body", "query"], msg: "Field required" },
    ];
    expect(detailToMessage(detail, 422)).toBe(
      "days: Input should be less than or equal to 14; query: Field required",
    );
  });

  test("falls back to the status line for unknown shapes", () => {
    expect(detailToMessage(undefined, 502)).toBe("Request failed with status 502");
    expect(detailToMessage({ odd: true }, 500)).toBe("Request failed with status 500");
  });
});
