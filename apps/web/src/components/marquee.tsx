const DESTINATIONS = [
  "Philadelphia",
  "New Orleans",
  "Nashville",
  "Tampa",
  "Indianapolis",
  "Tucson",
  "Reno",
  "Santa Barbara",
  "Boise",
  "Saint Louis",
  "Edmonton",
  "Wilmington",
];

/** Slow ribbon of charted cities — pauses on hover, hidden from readers. */
export function CityMarquee() {
  const row = DESTINATIONS.map((city, index) => (
    <span key={`${city}-${index}`} className="flex items-center">
      <span className="voice-display px-8 text-2xl font-light text-starlight/25 transition-colors hover:text-brass sm:text-3xl">
        {city}
      </span>
      <span className="text-brass/40" aria-hidden="true">
        ✦
      </span>
    </span>
  ));

  return (
    <div
      className="marquee relative overflow-hidden border-y border-(--line) py-5 [mask-image:linear-gradient(90deg,transparent,black_12%,black_88%,transparent)]"
      aria-hidden="true"
    >
      <div className="marquee-track">
        <div className="flex shrink-0 items-center">{row}</div>
        <div className="flex shrink-0 items-center">{row}</div>
      </div>
    </div>
  );
}
