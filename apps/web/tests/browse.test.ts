import { describe, expect, test } from "bun:test";

import { browseHref, type BrowseState } from "@/lib/browse";

const base: BrowseState = { openOnly: false, sort: "rating", page: 1 };

describe("browseHref", () => {
  test("defaults collapse to bare /browse", () => {
    expect(browseHref(base)).toBe("/browse");
  });

  test("serializes non-default state", () => {
    const href = browseHref({
      ...base,
      city: "Philadelphia",
      category: "Coffee & Tea",
      priceMax: 2,
      minStars: 4.5,
      openOnly: true,
      sort: "reviews",
      page: 3,
    });
    const url = new URL(`http://x${href}`);
    expect(url.pathname).toBe("/browse");
    expect(url.searchParams.get("city")).toBe("Philadelphia");
    expect(url.searchParams.get("category")).toBe("Coffee & Tea");
    expect(url.searchParams.get("price_max")).toBe("2");
    expect(url.searchParams.get("min_stars")).toBe("4.5");
    expect(url.searchParams.get("open")).toBe("on");
    expect(url.searchParams.get("sort")).toBe("reviews");
    expect(url.searchParams.get("page")).toBe("3");
  });

  test("overrides replace and can clear a facet", () => {
    const state: BrowseState = { ...base, city: "Tampa", page: 4 };
    expect(browseHref(state, { city: undefined, page: 1 })).toBe("/browse");
    expect(browseHref(state, { category: "Bakeries", page: 1 })).toBe(
      "/browse?city=Tampa&category=Bakeries",
    );
  });
});
