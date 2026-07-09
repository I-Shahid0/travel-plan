import { describe, expect, test } from "bun:test";

import { categoryHue, constellationFor, fnv1a } from "@/lib/constellation";

describe("constellation sigils", () => {
  test("same listing id always casts the same constellation", () => {
    const a = constellationFor("6_T2xzR74JqGCTPefAD8Tw", ["Japanese"]);
    const b = constellationFor("6_T2xzR74JqGCTPefAD8Tw", ["Japanese"]);
    expect(a).toEqual(b);
  });

  test("different ids cast different skies", () => {
    const a = constellationFor("listing-alpha", []);
    const b = constellationFor("listing-omega", []);
    expect(a.stars).not.toEqual(b.stars);
  });

  test("stars stay inside the 100×62.5 viewBox with margin", () => {
    for (const id of ["a", "bb", "ccc", "d-4", "e_5", "long-listing-id-000111"]) {
      const spec = constellationFor(id, []);
      expect(spec.stars.length).toBeGreaterThanOrEqual(5);
      expect(spec.stars.length).toBeLessThanOrEqual(8);
      for (const star of spec.stars) {
        expect(star.x).toBeGreaterThanOrEqual(10);
        expect(star.x).toBeLessThanOrEqual(90);
        expect(star.y).toBeGreaterThanOrEqual(9);
        expect(star.y).toBeLessThanOrEqual(53);
      }
    }
  });

  test("edges reference existing stars and form a connected walk", () => {
    const spec = constellationFor("edge-check", ["Coffee & Tea"]);
    expect(spec.edges.length).toBeGreaterThanOrEqual(spec.stars.length - 1);
    for (const [from, to] of spec.edges) {
      expect(spec.stars[from]).toBeDefined();
      expect(spec.stars[to]).toBeDefined();
    }
  });

  test("category hues land in their families", () => {
    expect(categoryHue(["Coffee & Tea"])).toBe(32);
    expect(categoryHue(["Sushi Bars", "Restaurants"])).toBe(350);
    expect(categoryHue(["Cocktail Bars", "Nightlife"])).toBe(268);
    expect(categoryHue(["Parks", "Hiking"])).toBe(152);
    expect(categoryHue(["Unclassifiable Oddity"])).toBe(226);
  });

  test("fnv1a is stable", () => {
    expect(fnv1a("meridian")).toBe(fnv1a("meridian"));
    expect(fnv1a("meridian")).not.toBe(fnv1a("meridiam"));
  });
});
