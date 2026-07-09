/**
 * Aurora light: two slow-drifting blurred colour fields blended over the sky.
 * Purely decorative — hidden from assistive tech, cheap to composite.
 */
export function Aurora({ dim = false }: { dim?: boolean }) {
  const opacity = dim ? 0.16 : 0.3;
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="aurora-blob aurora-a"
        style={{
          top: "-22%",
          left: "-12%",
          width: "58%",
          height: "70%",
          opacity,
          background:
            "radial-gradient(ellipse at center, rgba(94,234,212,0.75), rgba(94,234,212,0) 68%)",
        }}
      />
      <div
        className="aurora-blob aurora-b"
        style={{
          top: "-28%",
          right: "-14%",
          width: "64%",
          height: "78%",
          opacity,
          background:
            "radial-gradient(ellipse at center, rgba(139,124,255,0.7), rgba(139,124,255,0) 66%)",
        }}
      />
      <div
        className="aurora-blob aurora-a"
        style={{
          bottom: "-40%",
          left: "28%",
          width: "52%",
          height: "72%",
          opacity: opacity * 0.75,
          animationDelay: "-12s",
          background:
            "radial-gradient(ellipse at center, rgba(255,157,176,0.55), rgba(255,157,176,0) 64%)",
        }}
      />
    </div>
  );
}
