import { describe, expect, test } from "bun:test";

import { attributeBadges, parsePythonish, trueKeys } from "@/lib/attributes";

describe("parsePythonish", () => {
  test("booleans and None", () => {
    expect(parsePythonish("True")).toBe(true);
    expect(parsePythonish("False")).toBeNull();
    expect(parsePythonish("None")).toBeNull();
    expect(parsePythonish(undefined)).toBeNull();
  });

  test("unwraps python string quoting", () => {
    expect(parsePythonish("u'free'")).toBe("free");
    expect(parsePythonish("'casual'")).toBe("casual");
    expect(parsePythonish('u"full_bar"')).toBe("full_bar");
    expect(parsePythonish("plain")).toBe("plain");
  });
});

describe("trueKeys", () => {
  test("extracts only True entries from stringified dicts", () => {
    const raw = "{'romantic': False, 'intimate': True, 'classy': True, 'hipster': False}";
    expect(trueKeys(raw)).toEqual(["intimate", "classy"]);
  });

  test("empty for non-dicts", () => {
    expect(trueKeys("True")).toEqual([]);
    expect(trueKeys(null)).toEqual([]);
  });
});

describe("attributeBadges", () => {
  test("curates a realistic yelp attribute blob", () => {
    const badges = attributeBadges({
      WiFi: "u'free'",
      Alcohol: "u'beer_and_wine'",
      OutdoorSeating: "True",
      DogsAllowed: "False",
      NoiseLevel: "u'quiet'",
      RestaurantsAttire: "u'casual'",
      Ambience: "{'romantic': True, 'divey': False}",
      GoodForMeal: "{'brunch': True, 'latenight': True, 'dinner': False}",
      BusinessParking: "{'street': True, 'garage': False}",
    });
    const labels = badges.map((badge) => badge.label);
    expect(labels).toContain("Free Wi-Fi");
    expect(labels).toContain("Beer & wine");
    expect(labels).toContain("Outdoor seating");
    expect(labels).toContain("Quiet room");
    expect(labels).not.toContain("Dogs welcome");
    // casual attire is the default — not worth a badge
    expect(labels.find((label) => label.includes("attire"))).toBeUndefined();

    const meals = badges.find((badge) => badge.label === "Good for");
    expect(meals?.detail).toBe("brunch · late night");
    const parking = badges.find((badge) => badge.label === "Parking");
    expect(parking?.detail).toBe("street parking");
  });

  test("empty attributes produce no badges", () => {
    expect(attributeBadges({})).toEqual([]);
  });
});
