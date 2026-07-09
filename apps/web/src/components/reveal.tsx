"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Adds `.in` when the element scrolls into view — pairs with the `.stagger`
 * utility so children rise in sequence. Falls back to visible immediately
 * when IntersectionObserver is unavailable.
 */
export function Reveal({
  children,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "ul";
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      node.classList.add("in");
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            node.classList.add("in");
            observer.disconnect();
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Component = Tag as any;
  return (
    <Component ref={ref} className={`stagger ${className}`}>
      {children}
    </Component>
  );
}
