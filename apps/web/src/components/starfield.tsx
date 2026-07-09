"use client";

import { useEffect, useRef } from "react";

interface Star {
  x: number;
  y: number;
  r: number;
  depth: number;
  phase: number;
  speed: number;
}

/**
 * The living sky: parallax stars drifting on a slow current, twinkling out
 * of phase, with constellation lines materialising near the pointer.
 * Renders once as a static sky when the visitor prefers reduced motion.
 */
export function Starfield({ density = 1 }: { density?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let stars: Star[] = [];
    let raf = 0;
    let t = 0;
    const pointer = { x: -9999, y: -9999 };

    const seedStars = () => {
      const count = Math.floor((width * height) / 5200) * density;
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.15 + 0.35,
        depth: Math.random() * 0.75 + 0.25,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.5 + 0.5,
      }));
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.offsetWidth;
      height = canvas.offsetHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seedStars();
      if (reduceMotion) draw();
    };

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      // constellation lines near the pointer
      const reach = 130;
      const near = stars.filter((s) => {
        const dx = s.x - pointer.x;
        const dy = s.y - pointer.y;
        return dx * dx + dy * dy < reach * reach;
      });
      ctx.lineWidth = 0.6;
      for (let i = 0; i < near.length; i++) {
        for (let j = i + 1; j < near.length; j++) {
          const a = near[i];
          const b = near[j];
          if (!a || !b) continue;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 90) {
            const fade = 1 - dist / 90;
            ctx.strokeStyle = `rgba(139, 124, 255, ${0.35 * fade})`;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      for (const s of stars) {
        const tw = reduceMotion ? 0.75 : 0.55 + 0.45 * Math.sin(t * 0.9 * s.speed + s.phase);
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(233, 237, 255, ${0.28 + 0.62 * tw * s.depth})`;
        ctx.fill();
        // slow drift on a diagonal current, deeper stars slower
        if (!reduceMotion) {
          s.x += 0.016 * s.depth;
          s.y -= 0.008 * s.depth;
          if (s.x > width + 4) s.x = -4;
          if (s.y < -4) s.y = height + 4;
        }
      }
    };

    const loop = () => {
      t += 0.016;
      draw();
      raf = requestAnimationFrame(loop);
    };

    const onPointer = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointer.x = event.clientX - rect.left;
      pointer.y = event.clientY - rect.top;
    };
    const onLeave = () => {
      pointer.x = -9999;
      pointer.y = -9999;
    };

    resize();
    window.addEventListener("resize", resize);
    if (!reduceMotion) {
      window.addEventListener("pointermove", onPointer, { passive: true });
      window.addEventListener("pointerleave", onLeave);
      raf = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("pointerleave", onLeave);
    };
  }, [density]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
}
