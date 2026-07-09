/** Brass compass rose — the MERIDIAN mark. Rotates slowly where allowed. */
export function CompassRose({
  className = "h-6 w-6",
  spin = false,
}: {
  className?: string;
  spin?: boolean;
}) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <g className={spin ? "spin-slower origin-center" : undefined}>
        <circle cx="24" cy="24" r="22" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.35" />
        <circle cx="24" cy="24" r="16.5" fill="none" stroke="currentColor" strokeWidth="0.5" opacity="0.3" />
        {/* cardinal points */}
        <path d="M24 4 L26.4 21.6 L24 24 L21.6 21.6 Z" fill="currentColor" opacity="0.95" />
        <path d="M24 44 L26.4 26.4 L24 24 L21.6 26.4 Z" fill="currentColor" opacity="0.5" />
        <path d="M4 24 L21.6 21.6 L24 24 L21.6 26.4 Z" fill="currentColor" opacity="0.5" />
        <path d="M44 24 L26.4 21.6 L24 24 L26.4 26.4 Z" fill="currentColor" opacity="0.5" />
        {/* intercardinal ticks */}
        <g stroke="currentColor" strokeWidth="1" opacity="0.45">
          <line x1="9.9" y1="9.9" x2="13.4" y2="13.4" />
          <line x1="38.1" y1="9.9" x2="34.6" y2="13.4" />
          <line x1="9.9" y1="38.1" x2="13.4" y2="34.6" />
          <line x1="38.1" y1="38.1" x2="34.6" y2="34.6" />
        </g>
      </g>
      <circle cx="24" cy="24" r="2" fill="currentColor" />
    </svg>
  );
}
