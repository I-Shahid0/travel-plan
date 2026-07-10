/**
 * The Yelp dataset stores listing attributes as stringified Python literals:
 * "True", "u'free'", "{'romantic': False, 'classy': True}". This module
 * distills that soup into a curated set of human badges for the listing page.
 */

export interface AttributeBadge {
  label: string;
  detail?: string;
}

/** "u'free'" | "'free'" | "free" -> "free"; "True" -> true; "None" -> null */
export function parsePythonish(raw: unknown): string | boolean | null {
  if (typeof raw === "boolean") return raw;
  if (raw == null) return null;
  const text = String(raw).trim();
  if (text === "True") return true;
  if (text === "False" || text === "None" || text === "") return null;
  const unquoted = text.replace(/^u?'(.*)'$/s, "$1").replace(/^u?"(.*)"$/s, "$1");
  return unquoted;
}

/** Keys marked True inside a stringified Python dict. */
export function trueKeys(raw: unknown): string[] {
  if (raw == null) return [];
  const text = String(raw);
  const keys: string[] = [];
  const pattern = /'([^']+)':\s*True/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match[1]) keys.push(match[1]);
  }
  return keys;
}

const WORDY: Record<string, string> = {
  latenight: "late night",
  hipster: "hipster",
  divey: "divey",
  touristy: "touristy",
  trendy: "trendy",
  upscale: "upscale",
  classy: "classy",
  casual: "casual",
  romantic: "romantic",
  intimate: "intimate",
  dessert: "dessert",
  breakfast: "breakfast",
  brunch: "brunch",
  lunch: "lunch",
  dinner: "dinner",
  street: "street parking",
  lot: "parking lot",
  garage: "garage parking",
  valet: "valet",
  validated: "validated parking",
};

function humanize(key: string): string {
  return WORDY[key] ?? key.replace(/_/g, " ");
}

/** Simple yes-flags worth surfacing, in display order. */
const FLAGS: Array<[string, string]> = [
  ["RestaurantsReservations", "Takes reservations"],
  ["RestaurantsDelivery", "Delivers"],
  ["RestaurantsTakeOut", "Take-out"],
  ["OutdoorSeating", "Outdoor seating"],
  ["DogsAllowed", "Dogs welcome"],
  ["GoodForKids", "Good for kids"],
  ["RestaurantsGoodForGroups", "Good for groups"],
  ["WheelchairAccessible", "Wheelchair accessible"],
  ["HappyHour", "Happy hour"],
  ["Caters", "Caters"],
  ["BikeParking", "Bike parking"],
  ["HasTV", "Has a TV"],
  ["DriveThru", "Drive-thru"],
  ["ByAppointmentOnly", "By appointment only"],
];

export function attributeBadges(attributes: Record<string, unknown>): AttributeBadge[] {
  const badges: AttributeBadge[] = [];

  const wifi = parsePythonish(attributes.WiFi);
  if (wifi === "free") badges.push({ label: "Free Wi-Fi" });
  else if (wifi === "paid") badges.push({ label: "Paid Wi-Fi" });

  const alcohol = parsePythonish(attributes.Alcohol);
  if (alcohol === "full_bar") badges.push({ label: "Full bar" });
  else if (alcohol === "beer_and_wine") badges.push({ label: "Beer & wine" });

  const attire = parsePythonish(attributes.RestaurantsAttire);
  if (typeof attire === "string" && attire !== "casual") {
    badges.push({ label: `${humanize(attire)} attire` });
  }

  const noise = parsePythonish(attributes.NoiseLevel);
  if (noise === "quiet") badges.push({ label: "Quiet room" });
  else if (noise === "very_loud") badges.push({ label: "Loud & lively" });

  for (const [key, label] of FLAGS) {
    if (parsePythonish(attributes[key]) === true) badges.push({ label });
  }

  const ambience = trueKeys(attributes.Ambience).map(humanize);
  if (ambience.length > 0) {
    badges.push({ label: "Ambience", detail: ambience.join(" · ") });
  }

  const meals = trueKeys(attributes.GoodForMeal).map(humanize);
  if (meals.length > 0) {
    badges.push({ label: "Good for", detail: meals.join(" · ") });
  }

  const parking = trueKeys(attributes.BusinessParking).map(humanize);
  if (parking.length > 0) {
    badges.push({ label: "Parking", detail: parking.join(" · ") });
  }

  return badges;
}
