import { describe, expect, test } from "bun:test";

import { parseItinerary } from "@/lib/itinerary-parse";

const TEMPLATE_OUTPUT = `Itinerary for: weekend food tour in Philadelphia (2 day(s))
(Generated from top-ranked places — planner temporarily degraded.)

Day 1:
  1. Philly Foodies Tours — Tours, Walking Tours, Food Tours — Philadelphia
  2. City Food Tours — Hotels & Travel, Specialty Food, Food — Philadelphia

Day 2:
  1. StrEATS of Philly Food Tours — Tours, Event Planning & Services — Philadelphia
  2. Philadelphia Brewing Company — Breweries, Food, Local Flavor — Philadelphia`;

const LLM_OUTPUT = `Here's a practical two-day food tour of Philadelphia.

**Day 1: Old City classics**
1. **Philly Foodies Tours** - start with the guided walking tour
2. **Reading Terminal Market** - lunch among the stalls
Grab a rest before the evening.

## Day 2
- Philadelphia Brewing Company: afternoon tasting
- City Food Tours: farewell dinner crawl`;

describe("parseItinerary", () => {
  test("parses the degraded template planner output", () => {
    const parsed = parseItinerary(TEMPLATE_OUTPUT);
    expect(parsed.raw).toBeNull();
    expect(parsed.days).toHaveLength(2);
    expect(parsed.days[0]?.stops).toHaveLength(2);
    expect(parsed.days[0]?.stops[0]?.title).toBe("Philly Foodies Tours");
    expect(parsed.days[0]?.stops[0]?.detail).toContain("Walking Tours");
    expect(parsed.intro.length).toBeGreaterThan(0);
  });

  test("parses markdown-flavored LLM output", () => {
    const parsed = parseItinerary(LLM_OUTPUT);
    expect(parsed.raw).toBeNull();
    expect(parsed.days).toHaveLength(2);
    expect(parsed.days[0]?.heading).toBe("Old City classics");
    expect(parsed.days[0]?.stops[0]?.title).toBe("Philly Foodies Tours");
    expect(parsed.days[0]?.notes[0]).toContain("Grab a rest");
    expect(parsed.days[1]?.stops).toHaveLength(2);
    expect(parsed.days[1]?.stops[0]?.title).toBe("Philadelphia Brewing Company");
  });

  test("falls back to raw text when no day structure exists", () => {
    const parsed = parseItinerary("Just wander and eat where the light looks warm.");
    expect(parsed.raw).toBe("Just wander and eat where the light looks warm.");
    expect(parsed.days).toHaveLength(0);
  });
});
