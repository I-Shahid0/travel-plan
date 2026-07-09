/** Display helpers shared across pages. */

export function priceGlyphs(priceLevel: number | null | undefined): string | null {
  if (!priceLevel || priceLevel < 1) return null;
  return "$".repeat(Math.min(priceLevel, 4));
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

/** "Philadelphia, PA" — tolerates missing halves. */
export function placeLine(city: string | null, state: string | null): string | null {
  if (city && state) return `${city}, ${state}`;
  return city ?? state ?? null;
}

/** "39.95°N 75.17°W" — real listing coordinates as an atlas readout. */
export function formatCoordinates(
  latitude: number | null | undefined,
  longitude: number | null | undefined,
): string | null {
  if (latitude == null || longitude == null) return null;
  const latHemi = latitude >= 0 ? "N" : "S";
  const lonHemi = longitude >= 0 ? "E" : "W";
  return `${Math.abs(latitude).toFixed(2)}°${latHemi} ${Math.abs(longitude).toFixed(2)}°${lonHemi}`;
}
