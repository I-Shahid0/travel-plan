import { constellationFor } from "@/lib/constellation";

/**
 * A listing's constellation sigil — deterministic star chart derived from its
 * id, tinted by its leading category. Server-rendered SVG; no assets.
 */
export function ConstellationArt({
  id,
  categories,
  className,
}: {
  id: string;
  categories: string[];
  className?: string;
}) {
  const spec = constellationFor(id, categories);
  const gradId = `neb-${id.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 24)}`;

  return (
    <svg
      viewBox="0 0 100 62.5"
      className={className}
      role="img"
      aria-label="Constellation sigil"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        {/* night-sky base with a quiet category-hued nebula — tint, not paint */}
        <radialGradient id={`${gradId}-a`} cx="28%" cy="18%" r="80%">
          <stop offset="0%" stopColor={`hsl(${spec.hueA} 42% 24%)`} stopOpacity="0.55" />
          <stop offset="60%" stopColor={`hsl(${spec.hueA} 35% 12%)`} stopOpacity="0.25" />
          <stop offset="100%" stopColor="#04060e" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`${gradId}-b`} cx="78%" cy="82%" r="70%">
          <stop offset="0%" stopColor={`hsl(${spec.hueB} 45% 26%)`} stopOpacity="0.35" />
          <stop offset="100%" stopColor="#04060e" stopOpacity="0" />
        </radialGradient>
      </defs>

      <rect width="100" height="62.5" fill="#070b18" />
      <rect width="100" height="62.5" fill={`url(#${gradId}-a)`} />
      <rect width="100" height="62.5" fill={`url(#${gradId}-b)`} />

      {/* graticule etching */}
      <g stroke="rgba(233,237,255,0.05)" strokeWidth="0.25">
        <line x1="0" y1="21" x2="100" y2="21" />
        <line x1="0" y1="42" x2="100" y2="42" />
        <line x1="33" y1="0" x2="33" y2="62.5" />
        <line x1="66" y1="0" x2="66" y2="62.5" />
      </g>

      {/* constellation lines */}
      <g
        className="sigil-lines"
        stroke={`hsl(${spec.hueA} 80% 72% / 0.5)`}
        strokeWidth="0.35"
        strokeLinecap="round"
      >
        {spec.edges.map(([a, b], i) => {
          const from = spec.stars[a];
          const to = spec.stars[b];
          if (!from || !to) return null;
          return <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
        })}
      </g>

      {/* stars */}
      <g fill="#e9edff">
        {spec.stars.map((star, i) => (
          <g key={i}>
            {star.bright && (
              <circle cx={star.x} cy={star.y} r={star.r * 1.9} fill={`hsl(${spec.hueA} 80% 70% / 0.14)`} />
            )}
            <circle cx={star.x} cy={star.y} r={star.r * 0.8} opacity={star.bright ? 1 : 0.6} />
            {star.bright && (
              <g stroke="rgba(233,237,255,0.6)" strokeWidth="0.18">
                <line x1={star.x - star.r * 2.6} y1={star.y} x2={star.x + star.r * 2.6} y2={star.y} />
                <line x1={star.x} y1={star.y - star.r * 2.6} x2={star.x} y2={star.y + star.r * 2.6} />
              </g>
            )}
          </g>
        ))}
      </g>
    </svg>
  );
}
